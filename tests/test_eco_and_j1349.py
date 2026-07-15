# DEV NOTE: All code, comments, and variable names must be in English.
"""Golden tests for ECO winner semantics (BL-FABLE5-C1) and the vdyno
SAE J1349 temperature source (MAT, not IAT_Corr).

Synthetic data with analytically known answers. If any of these fail, the
map-merge / proposal pipeline cannot be trusted. Runnable with pytest or
directly: python tests/test_eco_and_j1349.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web.vs_engine as vs_engine
from web.vdyno import _seg_physics
from web.vs_engine import RPM_BINS, TPS_BINS, _bin_index, _eco_winner


def _cell_key(rpm: float, tps: float) -> tuple:
    return (_bin_index(rpm, RPM_BINS), _bin_index(tps, TPS_BINS))


def _sweet_row(rpm_lo: float, tps_lo: float, dpw_eff: float) -> dict:
    return {
        'na': 20, 'nb': 20, 'flavor': 'SWEET',
        'rpm_lo': rpm_lo, 'tps_lo': tps_lo,
        'pw_eff_a': 4.0, 'pw_eff_b': 4.0 + dpw_eff,
        'dpw_eff': dpw_eff, 'dpw_eff_sig': True,
    }


def _run_build_ci(rows: list, f7_matches: list | None = None) -> tuple:
    """Run _build_ci against synthetic compare output (no disk, no cache)."""
    orig_cmp = vs_engine._compare_sessions_cached
    orig_gpr = vs_engine._gpr_predict_grid
    vs_engine._compare_sessions_cached = (
        lambda d, a, b: {'delta': rows, 'f7_matches': f7_matches or []})
    vs_engine._gpr_predict_grid = lambda delta, flavor='SWEET': {}
    try:
        return vs_engine._build_ci(Path('.'), 'SYN_A', 'SYN_B')
    finally:
        vs_engine._compare_sessions_cached = orig_cmp
        vs_engine._gpr_predict_grid = orig_gpr


def test_eco_winner_picks_the_leaner_map() -> None:
    # dpw_eff = B - A. Positive -> B injects more -> A is the eco winner.
    assert _eco_winner(0.5) == 'A'
    assert _eco_winner(-0.5) == 'B'


def test_build_ci_eco_labels_from_vs_only() -> None:
    rows = [
        _sweet_row(2400, 20, -0.5),  # B injects less -> eco B
        _sweet_row(3200, 30, +0.5),  # B injects more -> eco A
    ]
    ci, _delta, _stats = _run_build_ci(rows)
    assert ci[_cell_key(2400, 20)]['eco'] == 'B'
    assert ci[_cell_key(3200, 30)]['eco'] == 'A'


def test_build_ci_f7_conflict_abstains() -> None:
    # VS says B is leaner (-0.5) but F7 says B is richer (+0.3): conflicting
    # evidence -> no eco decision for that cell.
    rows = [_sweet_row(2400, 20, -0.5)]
    f7_matches = [{
        # tps_peak must land in the same TPS bin as the VS row's tps_lo (20)
        # for the fusion lookup to hit; 22 -> bin [20,25), zone LIGHT.
        'bucket_a': {'rpm_center': 2400, 'tps_peak': 22},
        'bucket_b': {'tps_peak': 22},
        'delta_pw': [0.3, 0.3],
        'tps_dtw': 1.0,
    }]
    ci, _delta, stats = _run_build_ci(rows, f7_matches)
    assert ci[_cell_key(2400, 20)]['eco'] is None
    assert stats['skipped_conflicting_f7'] == 1


def test_build_ci_f7_agreement_fuses_and_labels() -> None:
    # Both sources say B is leaner -> fused delta negative -> eco B.
    rows = [_sweet_row(2400, 20, -0.5)]
    f7_matches = [{
        # tps_peak must land in the same TPS bin as the VS row's tps_lo (20)
        # for the fusion lookup to hit; 22 -> bin [20,25), zone LIGHT.
        'bucket_a': {'rpm_center': 2400, 'tps_peak': 22},
        'bucket_b': {'tps_peak': 22},
        'delta_pw': [-0.3, -0.3],
        'tps_dtw': 1.0,
    }]
    ci, _delta, stats = _run_build_ci(rows, f7_matches)
    assert ci[_cell_key(2400, 20)]['eco'] == 'B'
    assert stats['fused_with_f7'] == 1


def test_sport_winner_unchanged() -> None:
    # ddvss = B - A speed gain. Positive -> B accelerates better -> sport B.
    rows = [{
        'na': 20, 'nb': 20, 'flavor': 'SPICY_WOT',
        'rpm_lo': 4000, 'tps_lo': 90,
        'pw_eff_a': 6.0, 'pw_eff_b': 6.0, 'ddvss': 1.2,
    }]
    ci, _delta, _stats = _run_build_ci(rows)
    assert ci[_cell_key(4000, 90)]['sport'] == 'B'


def _vdyno_rows(**extra) -> list:
    # Constant 72 km/h (20 m/s), flat: aero + rolling power only, all rows > 0 W.
    return [{'time_elapsed_s': i * 0.125, 'VS_KPH': 72.0, 'RPM': 4000.0, **extra}
            for i in range(40)]


_VDYNO_CFG = {'mass_kg': 295.0, 'rho': 1.10, 'CdA': 0.60, 'Crr': 0.015,
              'smooth_s': 1.0, 'min_seg_s': 1.0}


def test_j1349_uses_mat() -> None:
    base = _seg_physics(_vdyno_rows(), _VDYNO_CFG)
    corr = _seg_physics(_vdyno_rows(MAT=25.0, baro_hPa=1013.0), _VDYNO_CFG)
    cf = float(np.median(corr[3] / base[3]))
    # J1349 at 25 C / 1013 hPa: (29.23/29.914) * sqrt((77+460)/537) = 0.9771
    assert abs(cf - 0.9771) < 0.005, f'correction factor {cf}'


def test_j1349_ignores_iat_corr() -> None:
    # IAT_Corr is a percent factor (92-118), not a temperature. Feeding it as
    # Celsius used to inflate power ~10-12%. It must no longer correct anything.
    base = _seg_physics(_vdyno_rows(), _VDYNO_CFG)
    bug = _seg_physics(_vdyno_rows(IAT_Corr=100.0, baro_hPa=1013.0), _VDYNO_CFG)
    assert np.allclose(bug[3], base[3])


def test_j1349_rejects_implausible_mat() -> None:
    # A MAT outside -20..60 C means a decode problem -> no correction.
    base = _seg_physics(_vdyno_rows(), _VDYNO_CFG)
    junk = _seg_physics(_vdyno_rows(MAT=100.0, baro_hPa=1013.0), _VDYNO_CFG)
    assert np.allclose(junk[3], base[3])


if __name__ == '__main__':
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f'PASS {name}')
            except AssertionError as e:
                fails += 1
                print(f'FAIL {name}: {e}')
    sys.exit(1 if fails else 0)
