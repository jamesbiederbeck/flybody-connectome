"""Continuous (DC/tonic) stimulation strength on the two responsive SApp cells.

Companion to `haltere_sapp_pulse.py`'s spike-timed drive: this is the sustained
tonic-current regime `haltere_axis_pairs.py`/`haltere_single_cell.py` already
use elsewhere in this repo. `haltere_single_cell.py`'s coarse 8/14/20 mV grid
found both cells silent at 8/14 mV and firing hard at 20 mV; this refines that
to a 1 mV grid and asks three questions:

  3a. Each cell's own threshold, swept individually from 20 mV down to 0.
  3b. Whether driving both together lowers the threshold below either cell's
      own -- sub-threshold summation at a shared target, explicitly flagged as
      untested in this log's 2026-09-19 single-cell-sweep entry ("silent alone
      is not the same as contributing nothing in combination").
  3c. At the combined drive's Euclidean magnitude fixed at the value implied by
      3b's joint threshold, whether the *direction* of the (V_L, V_R) vector --
      not just its magnitude -- matters. Operationalized as: M =
      sqrt(2) * V_joint (since 3b drives both cells equally at V_joint each,
      giving magnitude sqrt(V_joint^2 + V_joint^2)); sweep angle theta from 0
      to 90 degrees at fixed M, with V_L = M*cos(theta), V_R = M*sin(theta).
      theta=45 deg reproduces 3b's equal-drive point; theta=0/90 deg drive only
      one cell at the full magnitude M. This is a genuine 2D-vector sweep, not
      a fixed-sum allocation -- all points share the same Euclidean norm.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

SAPP_R_BODY_ID = "101048"
SAPP_L_BODY_ID = "136883"
SUSTAIN_MS = 500.0  # matches haltere_axis_pairs.SUSTAIN_MS
DLM_TYPES = ["DLMn a, b", "DLMn c-f"]
N_ANGLES = 9  # 0, 11.25, ..., 90 degrees


def _find_cell(brain, body_id: str) -> np.ndarray:
    ids = np.asarray(brain.ids).astype(str)
    idx = np.flatnonzero(ids == body_id)
    if len(idx) != 1:
        raise ValueError(f"Expected exactly one match for body_id {body_id}, got {len(idx)}")
    return idx.astype(np.int32)


def _dlm_readout(ann) -> dict:
    from experiments.haltere_axis_pairs import _side_of
    motor = (ann.superclass.astype(str) == "vnc_motor").to_numpy()
    types = ann.type.to_numpy()
    side = np.array([_side_of(i) for i in ann.instance.to_numpy()])
    out = {}
    for s in ("L", "R"):
        idx = np.flatnonzero(motor & np.isin(types, DLM_TYPES) & (side == s))
        out[f"DLM_{s}"] = idx.astype(np.int32)
    return out


def _all_groups(ann) -> dict:
    from experiments.haltere_axis_pairs import _readouts
    return {**_readouts(ann), **_dlm_readout(ann)}


def _trial(brain, dark, groups, stim, duration_ms=SUSTAIN_MS) -> dict:
    from experiments.haltere_axis_pairs import _reset
    _reset(brain)
    c, _ = brain.step(dark, duration_ms, stimulation=stim)
    dlm = int(c[groups["DLM_L"]].sum() + c[groups["DLM_R"]].sum())
    row = {"dlm_total": dlm, "global_total": int(c.sum())}
    for k, ix in groups.items():
        row[k] = int(c[ix].sum())
    return row


def sweep_individual(brain, dark, groups, idx, voltages) -> list:
    rows = []
    for v in voltages:
        stim = (idx, float(v)) if v > 0 else None
        row = {"voltage_mV": v, **_trial(brain, dark, groups, stim)}
        rows.append(row)
        print(f"  V={v:5.1f} mV  DLM={row['dlm_total']:6d}  global={row['global_total']:6d}",
              flush=True)
    # Reset verification: re-run the first voltage and require an exact
    # match (haltere_axis_pairs.py's "the reset is verified rather than
    # assumed" convention).
    stim0 = (idx, float(voltages[0])) if voltages[0] > 0 else None
    check = _trial(brain, dark, groups, stim0)
    first = {k: v for k, v in rows[0].items() if k != "voltage_mV"}
    if check != first:
        keys = ("dlm_total", "global_total")
        raise RuntimeError(
            "State reset is not clean: repeating the first voltage "
            f"({voltages[0]} mV) gave {[check[k] for k in keys]} vs the first "
            f"run's {[first[k] for k in keys]}. Every result in this sweep "
            "is suspect.")
    return rows


def _find_threshold(rows) -> dict:
    """Lowest voltage with nonzero DLM response, and the highest with zero.

    Reported unconditionally (not "the highest zero below the lowest
    nonzero") because this pathway is documented non-monotone in current
    elsewhere in this repo; if v_off ends up above v_on that is itself a
    finding (a non-monotone response), not a computation to hide.
    """
    key = "voltage_mV" if "voltage_mV" in rows[0] else "voltage_each_mV"
    on = [r[key] for r in rows if r["dlm_total"] > 0]
    off = [r[key] for r in rows if r["dlm_total"] == 0]
    v_on = min(on) if on else None
    v_off = max(off) if off else None
    return {"v_on_lowest_nonzero_dlm": v_on, "v_off_highest_zero_dlm": v_off,
            "monotone": (v_off is None or v_on is None or v_off < v_on)}


def run(*, dataset="malecns_v1", out=ROOT / "outputs/haltere_sapp_threshold.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    groups = _all_groups(ann)
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    r_idx = _find_cell(brain, SAPP_R_BODY_ID)
    l_idx = _find_cell(brain, SAPP_L_BODY_ID)
    voltages_1mv = [float(v) for v in range(20, -1, -1)]  # 20, 19, ..., 0

    started = time.time()
    print("=== 3a: individual threshold sweep ===", flush=True)
    print("-- R (101048) --", flush=True)
    rows_r = sweep_individual(brain, dark, groups, r_idx, voltages_1mv)
    print("-- L (136883) --", flush=True)
    rows_l = sweep_individual(brain, dark, groups, l_idx, voltages_1mv)
    thr_r = _find_threshold(rows_r)
    thr_l = _find_threshold(rows_l)
    print(f"R threshold: {thr_r}", flush=True)
    print(f"L threshold: {thr_l}", flush=True)

    print("\n=== 3b: joint threshold ===", flush=True)
    v_on_r = thr_r["v_on_lowest_nonzero_dlm"]
    v_on_l = thr_l["v_on_lowest_nonzero_dlm"]
    v0 = max(v_on_r, v_on_l) + 1.0
    joint_voltages = [round(v0 - 0.5 * k, 2) for k in range(int(v0 * 2) + 2)]
    joint_voltages = [v for v in joint_voltages if v >= 0]
    idx_both = np.concatenate([l_idx, r_idx])
    rows_joint = []
    for v in joint_voltages:
        # No early break: this pathway is documented non-monotone in current
        # elsewhere in this repo (AGENTS.md; LOG.md's leave-one-out entry,
        # 1061 -> 653 -> 597), so a single zero mid-sweep does not mean every
        # lower voltage is also zero. Sweep the full range and let
        # _find_threshold take the true min over all of it.
        stim = (idx_both, float(v)) if v > 0 else None
        row = {"voltage_each_mV": v, **_trial(brain, dark, groups, stim)}
        rows_joint.append(row)
        print(f"  V_each={v:5.1f} mV  DLM={row['dlm_total']:6d}  global={row['global_total']:6d}",
              flush=True)
    thr_joint = _find_threshold(rows_joint)
    v_joint = thr_joint["v_on_lowest_nonzero_dlm"]
    print(f"Joint threshold (V_each): {thr_joint}", flush=True)
    print(f"Individual thresholds were R={v_on_r} L={v_on_l}; joint={v_joint}", flush=True)

    print("\n=== 3c: direction sweep at fixed Euclidean magnitude ===", flush=True)
    if v_joint is None:
        raise RuntimeError("3b found no joint threshold in range; cannot fix magnitude for 3c")
    M = float(np.sqrt(2.0) * v_joint)
    thetas = np.linspace(0.0, 90.0, N_ANGLES)
    rows_direction = []
    for theta_deg in thetas:
        theta = np.deg2rad(theta_deg)
        v_l = M * np.cos(theta)
        v_r = M * np.sin(theta)
        stim = []
        if v_l > 0:
            stim.append((l_idx, float(v_l)))
        if v_r > 0:
            stim.append((r_idx, float(v_r)))
        row = {"theta_deg": round(float(theta_deg), 2), "V_L_mV": round(float(v_l), 3),
              "V_R_mV": round(float(v_r), 3), "magnitude_mV": M,
              **_trial(brain, dark, groups, stim or None)}
        rows_direction.append(row)
        print(f"  theta={theta_deg:6.2f} deg  V_L={v_l:6.2f} V_R={v_r:6.2f}  "
              f"DLM={row['dlm_total']:6d}  global={row['global_total']:6d}", flush=True)

    report = {
        "dataset": dataset, "sustain_ms": SUSTAIN_MS,
        "sapp_r_body_id": SAPP_R_BODY_ID, "sapp_l_body_id": SAPP_L_BODY_ID,
        "individual": {
            "voltages_mV": voltages_1mv,
            "R_101048": {"rows": rows_r, "threshold": thr_r},
            "L_136883": {"rows": rows_l, "threshold": thr_l},
        },
        "joint": {
            "v0_just_above_max_individual_threshold": v0,
            "voltages_each_mV": joint_voltages, "rows": rows_joint,
            "threshold": thr_joint,
            "lower_than_individual": (
                v_joint is not None and v_joint < min(v_on_r, v_on_l)),
        },
        "direction": {
            "definition": "Euclidean magnitude M = sqrt(2) * V_joint fixed; "
                          "V_L = M*cos(theta), V_R = M*sin(theta), theta swept "
                          "0 to 90 degrees",
            "magnitude_mV": M, "n_angles": N_ANGLES, "rows": rows_direction,
        },
        "wall_seconds": round(time.time() - started, 1),
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_sapp_threshold.json"))
    a = p.parse_args()
    r = run(out=a.out)
    print(f"\ndone in {r['wall_seconds']} s -> {a.out}")
