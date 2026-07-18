# DEV NOTE: All code, comments, and variable names must be in English.
"""web/o2.py -- narrowband O2 (rear cylinder) as a rich/lean comparator.

The bike runs Open Loop: EGO_Corr and AFV are locked at 100 and stay dead
until a wideband exists (that rule is intact -- nothing here touches them).
The RAW sensor pin (CSV column O2_ADC, RT offset 34, 2 bytes) IS alive:
real 0-0.88 V switching validated across all 14 logged sessions (IDEA-036).

A narrowband cell only says WHICH SIDE of stoichiometric the mixture is on;
it is a comparator, never an AFR meter:
- > NB_RICH_V  -> rich side
- < NB_LEAN_V  -> lean side
- in between / crossing both -> switching around stoich
Rear cylinder only (no front sensor). Every sample must be gated by
fl_o2_active=1 -- a cold/unlit sensor reads low regardless of mixture.

Thresholds and dominance rule were bench-tested in buell_fable5 v2.7.286
(measure/o2.py, 8 golden tests) before this port. Field validation on
47BF04 R2: cruise cells rich 0.60-0.76 V, decel fuel cut snaps to 0 V,
and a sustained-load lean window (23% TPS, 3250-3500 RPM, 0.00 V for 3 s
with fl_o2_active=1, instant recovery on throttle close) that coincides
with the glassbox cell-cube rear-lean region (2900-3400 RPM, Load 20-40).
"""
from __future__ import annotations

from typing import Dict, Optional

O2_ADC_TO_V = 5.0 / 1023.0   # 10-bit ADC on the 5 V reference
NB_RICH_V = 0.60
NB_LEAN_V = 0.30
NB_DOMINANT_FRAC = 0.70      # fraction on one side to earn a label
MIN_SAMPLES = 4              # fewer gated samples than this -> no label


def classify_o2_counts(n: int, rich_n: int, lean_n: int,
                       v_sum: float) -> Dict[str, Optional[float]]:
    """Rich/lean summary from per-cell counters (fl_o2_active-gated rows).

    Returns o2_n, o2_v_mean, o2_rich_frac, o2_lean_frac, o2_label
    ('rich' | 'lean' | 'switching'); label/means are None below MIN_SAMPLES.
    """
    if n < MIN_SAMPLES:
        return {'o2_n': n, 'o2_v_mean': None, 'o2_rich_frac': None,
                'o2_lean_frac': None, 'o2_label': None}
    rich = rich_n / n
    lean = lean_n / n
    if rich >= NB_DOMINANT_FRAC:
        label = 'rich'
    elif lean >= NB_DOMINANT_FRAC:
        label = 'lean'
    else:
        label = 'switching'
    return {'o2_n': n, 'o2_v_mean': round(v_sum / n, 3),
            'o2_rich_frac': round(rich, 3), 'o2_lean_frac': round(lean, 3),
            'o2_label': label}


def eco_lean_veto(winner: Optional[str], o2_a: Optional[str],
                  o2_b: Optional[str]) -> bool:
    """IDEA-036 safety veto: the ECO winner is the LEANER map for a cell.
    If that winner's own cell already reads LEAN on the narrowband, taking
    the proposal toward it removes fuel from a cell that is lean today --
    block the decision (abstain). No O2 data -> no veto (comparator only
    vetoes on positive lean evidence, never on absence of signal).
    """
    if winner == 'A':
        return o2_a == 'lean'
    if winner == 'B':
        return o2_b == 'lean'
    return False
