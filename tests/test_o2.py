# DEV NOTE: All code, comments, and variable names must be in English.
"""Golden tests for the NB O2 comparator (web/o2.py, IDEA-036).

Ported from buell_fable5 v2.7.286 (measure/o2.py, bench-validated there)
adapted to the per-cell counter API this repo uses in launch.build_index.
Runnable with pytest or directly: python tests/test_o2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.o2 import (
    MIN_SAMPLES, NB_DOMINANT_FRAC, NB_LEAN_V, NB_RICH_V, O2_ADC_TO_V,
    classify_o2_counts, eco_lean_veto)


def test_adc_conversion_matches_logger_constant():
    assert abs(O2_ADC_TO_V - 0.004887585) < 1e-8


def test_rich_cell_labeled_rich():
    r = classify_o2_counts(n=100, rich_n=100, lean_n=0, v_sum=70.0)
    assert r['o2_label'] == 'rich', r
    assert r['o2_rich_frac'] == 1.0
    assert r['o2_v_mean'] == 0.7


def test_lean_cell_labeled_lean():
    r = classify_o2_counts(n=100, rich_n=0, lean_n=100, v_sum=5.0)
    assert r['o2_label'] == 'lean', r
    assert r['o2_lean_frac'] == 1.0


def test_switching_cell_half_and_half():
    """A real NB at stoich crosses both thresholds -- neither side dominates."""
    r = classify_o2_counts(n=100, rich_n=50, lean_n=50, v_sum=45.0)
    assert r['o2_label'] == 'switching', r


def test_mid_band_cell_is_switching():
    r = classify_o2_counts(n=100, rich_n=0, lean_n=0, v_sum=45.0)
    assert r['o2_label'] == 'switching', r


def test_dominance_threshold_is_70_pct():
    below = classify_o2_counts(n=100, rich_n=int(NB_DOMINANT_FRAC * 100) - 1,
                               lean_n=0, v_sum=60.0)
    at = classify_o2_counts(n=100, rich_n=int(NB_DOMINANT_FRAC * 100),
                            lean_n=0, v_sum=60.0)
    assert below['o2_label'] == 'switching'
    assert at['o2_label'] == 'rich'


def test_too_few_samples_gives_no_label():
    r = classify_o2_counts(n=MIN_SAMPLES - 1, rich_n=MIN_SAMPLES - 1,
                           lean_n=0, v_sum=2.0)
    assert r['o2_label'] is None
    assert r['o2_v_mean'] is None
    assert r['o2_n'] == MIN_SAMPLES - 1


def test_thresholds_are_the_validated_ones():
    assert NB_RICH_V == 0.60 and NB_LEAN_V == 0.30


def test_eco_veto_blocks_lean_winner():
    assert eco_lean_veto('A', 'lean', 'rich') is True
    assert eco_lean_veto('B', 'rich', 'lean') is True


def test_eco_veto_allows_rich_or_switching_winner():
    assert eco_lean_veto('A', 'rich', 'lean') is False
    assert eco_lean_veto('B', 'lean', 'switching') is False


def test_eco_veto_never_fires_without_evidence():
    assert eco_lean_veto('A', None, None) is False
    assert eco_lean_veto(None, 'lean', 'lean') is False


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS {name}')
            except AssertionError as exc:
                failures += 1
                print(f'FAIL {name}: {exc}')
    sys.exit(1 if failures else 0)
