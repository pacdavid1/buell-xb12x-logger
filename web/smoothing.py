# DEV NOTE: All code, comments, and variable names must be in English.
# AI agents: write everything in English.
"""
smoothing.py — FASE 6: delta map interpolation and Laplacian smoothing.

Provides two-step smoothing for 12x13 EEPROM fuel/spark delta maps:
  1. IDW interpolation to fill cells without signal
  2. Laplacian smoothing with convergence-based termination

Dependencies: numpy (standard on Raspberry Pi)
Optional: scipy (for bicubic interpolation, falls back gracefully)
"""

import numpy as np

# --------------------------------------------------------------------------
# Module-level constants
# --------------------------------------------------------------------------

LAPLACIAN_LAMBDA_FUEL = 0.25
LAPLACIAN_LAMBDA_SPARK = 0.10
CONVERGENCE_FUEL = 0.5
CONVERGENCE_SPARK = 0.2
MAX_ITERATIONS = 6
MIN_SIGNAL_CELLS = 4
DELTA_CLAMP_FUEL = 15
DELTA_CLAMP_SPARK = 2
MIN_DELTA_FUEL = 0.5
MIN_DELTA_SPARK = 0.2


def interpolate_fill(grid, signal_mask):
    """
    Fill NaN/empty cells in a 2D grid using inverse-distance weighted
    interpolation from all signal-bearing cells.
    """
    result = grid.copy()
    rows, cols = grid.shape

    signal_r, signal_c = np.where(signal_mask)
    signal_vals = grid[signal_mask]

    valid = ~np.isnan(signal_vals)
    signal_r = signal_r[valid]
    signal_c = signal_c[valid]
    signal_vals = signal_vals[valid]

    n_signal = len(signal_vals)
    if n_signal < MIN_SIGNAL_CELLS:
        return result

    for r in range(rows):
        for c in range(cols):
            if signal_mask[r, c]:
                continue
            dr = signal_r - r
            dc = signal_c - c
            dists = np.sqrt(dr.astype(float)**2 + dc.astype(float)**2)
            dists = np.maximum(dists, 0.001)
            weights = 1.0 / dists
            result[r, c] = np.average(signal_vals, weights=weights)

    return result


def laplacian_smooth(grid, signal_mask, lambda_, max_iter, threshold):
    """
    Apply Laplacian smoothing on a 2D grid.
    Signal cells are smoothed at half strength.
    Rich/retard bias (1.1x) applied on final iteration only.
    """
    result = grid.copy().astype(float)
    rows, cols = grid.shape

    for iteration in range(max_iter):
        is_final = (iteration == max_iter - 1)
        new_grid = result.copy()
        max_change = 0.0

        for r in range(rows):
            for c in range(cols):
                neighbours = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        neighbours.append(result[nr, nc])

                if not neighbours:
                    continue

                avg = sum(neighbours) / len(neighbours)

                if is_final:
                    pos = [v for v in neighbours if v > 0]
                    neg = [v for v in neighbours if v < 0]
                    if pos and neg:
                        biased_sum = sum(pos) * 1.1 + sum(neg)
                        total_weight = len(pos) * 1.1 + len(neg)
                        avg = biased_sum / total_weight

                if signal_mask[r, c]:
                    blend = lambda_ * 0.5
                else:
                    blend = lambda_

                new_val = (1.0 - blend) * result[r, c] + blend * avg
                change = abs(new_val - result[r, c])
                if change > max_change:
                    max_change = change
                new_grid[r, c] = new_val

        result = new_grid

        if max_change < threshold:
            break

    return result


def smooth_map(delta_map, signal_mask, map_type="fuel"):
    """
    Full smoothing pipeline: clamp -> interpolate -> smooth -> second clamp -> floor.
    """
    if map_type == "fuel":
        lambda_ = LAPLACIAN_LAMBDA_FUEL
        threshold = CONVERGENCE_FUEL
        clamp_max = DELTA_CLAMP_FUEL
        min_delta = MIN_DELTA_FUEL
    elif map_type == "spark":
        lambda_ = LAPLACIAN_LAMBDA_SPARK
        threshold = CONVERGENCE_SPARK
        clamp_max = DELTA_CLAMP_SPARK
        min_delta = MIN_DELTA_SPARK
    else:
        raise ValueError("map_type must be fuel or spark, got: " + str(map_type))

    n_signal = int(np.sum(signal_mask))
    if n_signal < MIN_SIGNAL_CELLS:
        return delta_map

    # Step 1: Safety clamp
    delta_map = np.clip(delta_map, -clamp_max, clamp_max)

    # Step 2: Interpolate
    filled = interpolate_fill(delta_map, signal_mask)

    # Step 3: Smooth
    smoothed = laplacian_smooth(filled, signal_mask, lambda_=lambda_, max_iter=MAX_ITERATIONS, threshold=threshold)

    # Step 4: Second clamp
    smoothed = np.clip(smoothed, -clamp_max, clamp_max)

    # Step 5: Zero out sub-threshold deltas
    smoothed[np.abs(smoothed) < min_delta] = 0.0

    return smoothed


def smooth_all_maps(delta_front, delta_rear, signal_mask, map_type="fuel"):
    """Smooth both front and rear maps with shared signal mask."""
    front = smooth_map(delta_front, signal_mask, map_type)
    rear = smooth_map(delta_rear, signal_mask, map_type)
    return front, rear
