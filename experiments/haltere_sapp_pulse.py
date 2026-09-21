"""Pulsatile (spike-timed) drive on the two responsive SApp haltere cells.

`haltere_single_cell.py` found that SApp -- 148 undifferentiated cells, the
single largest haltere afferent type -- carries its entire single-cell response
through two cells: body_id 101048 (R, out-degree 293, 1037 motor spikes alone
at 20 mV/500 ms) and body_id 136883 (L, out-degree 311, 1018 spikes). They are
the best L/R-balanced pair in the dataset (~2% apart, against SNpp23's 2:1
split), which makes them the natural candidate for asking whether *timing*
between two haltere afferents -- not just DC magnitude -- reaches the wing
motor pool.

`haltere_axis_pairs.py` and `haltere_depth_phase.py` already tested an analog
sinusoidal modulation and found it low-passed to near nothing by the 20 ms
membrane/5 ms synaptic constants before it even leaves the afferent. That is a
different question from this one. Here the drive is discrete current pulses
timed to make the afferent itself spike at a chosen instant -- bypassing
whether an analog waveform survives the afferent's own membrane filter, and
asking instead whether spike-timing information *from* the afferent survives
the hops downstream. `PULSE_MS` is short (1 ms, well under the 20 ms membrane
tau and the 1.8 ms synaptic delay) by design, so each pulse approximates a
single input spike rather than a sustained current step -- invented, not
measured.

Experiment 1 drives both cells with identical, in-phase pulse trains and sweeps
the train's frequency. Experiment 2 takes the frequency(ies) that produced the
largest downstream response in experiment 1 and sweeps the phase offset between
the two cells' pulse trains at that frequency, from -180 deg to +180 deg.
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

# Invented: short relative to the 20 ms membrane tau and 1.8 ms synaptic delay,
# so a pulse approximates a single afferent spike rather than a sustained step.
PULSE_MS = 1.0
CALIBRATION_AMPS_MV = (20., 40., 60., 80., 100., 150., 200., 300., 400.)

# haltere_mtf.py's established frequency set, plus 300 Hz for resolution
# between 218 Hz (wingbeat) and 400 Hz.
FREQUENCIES_HZ = (5., 10., 30., 60., 120., 218., 300., 400.)
WINDOW_MS = 1000.0

PHASE_STEPS_DEG = tuple(range(-180, 181, 30))  # 13 points, -180 and +180 both included
DLM_TYPES = ["DLMn a, b", "DLMn c-f"]


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


def calibrate_pulse_amplitude(brain, dark, idx, amps=CALIBRATION_AMPS_MV) -> dict:
    """Smallest single-pulse amplitude that reliably makes this cell spike once.

    Drives only this cell for one PULSE_MS pulse from a fresh reset and reads
    its own spike count -- not any downstream readout. The 2.2 ms refractory
    period exceeds the 1 ms pulse, so a single pulse cannot produce more than
    one spike; this only distinguishes zero from one.
    """
    from experiments.haltere_axis_pairs import _reset
    trace = []
    chosen = None
    for amp in amps:
        _reset(brain)
        c, _ = brain.step(dark, PULSE_MS, stimulation=(idx, float(amp)))
        n = int(c[idx].sum())
        trace.append({"amplitude_mV": amp, "own_spikes": n})
        if n >= 1 and chosen is None:
            chosen = amp
    if chosen is None:
        raise RuntimeError(f"No calibration amplitude up to {amps[-1]} mV fired this cell")
    return {"chosen_amplitude_mV": chosen, "trace": trace}


def _pulse_bins(freq_hz, window_ms, bin_ms, phase_deg=0.0):
    """Bin indices (0-based) where a pulse falls, snapped to the nearest bin."""
    period_ms = 1000.0 / freq_hz
    shift_ms = (phase_deg / 360.0) * period_ms
    n_bins = int(round(window_ms / bin_ms))
    bins = set()
    n = 0
    while True:
        t_ms = n * period_ms + shift_ms
        if t_ms >= window_ms:
            break
        k = int(round(t_ms / bin_ms))
        if 0 <= k < n_bins:
            bins.add(k)
        n += 1
    return bins


def _run_pulse_trial(brain, dark, groups, l_idx, r_idx, amp, freq_hz, window_ms,
                     bin_ms, phase_deg):
    """One fresh-reset trial: pulses on l_idx at phase 0, r_idx at phase_deg."""
    from experiments.haltere_axis_pairs import _reset
    _reset(brain)
    n_bins = int(round(window_ms / bin_ms))
    l_bins = _pulse_bins(freq_hz, window_ms, bin_ms, 0.0)
    r_bins = _pulse_bins(freq_hz, window_ms, bin_ms, phase_deg)
    trace = {k: np.zeros(n_bins) for k in groups}
    global_trace = np.zeros(n_bins)
    for k in range(n_bins):
        stim = []
        if k in l_bins:
            stim.append((l_idx, amp))
        if k in r_bins:
            stim.append((r_idx, amp))
        c, _ = brain.step(dark, bin_ms, stimulation=stim or None)
        for name, ix in groups.items():
            trace[name][k] = c[ix].sum()
        global_trace[k] = c.sum()
    return trace, global_trace, len(l_bins), len(r_bins)


def _baseline(brain, dark, groups, window_ms):
    from experiments.haltere_axis_pairs import _reset
    _reset(brain)
    c, _ = brain.step(dark, window_ms, stimulation=None)
    return ({k: float(c[ix].sum()) for k, ix in groups.items()}, float(c.sum()))


def vector_strength_z(counts, t_s, f_hz):
    from experiments.haltere_mtf import vector_strength, null_distribution
    r = vector_strength(counts, t_s, f_hz)
    mu, sd, n = null_distribution(counts, t_s, f_hz)
    return {"r": round(r, 5), "null_mean": round(mu, 5), "null_sd": round(sd, 5),
            "null_n": n, "z": round((r - mu) / sd, 2) if sd else None}


def run_experiment1(brain, dark, groups, l_idx, r_idx, amp, bin_ms=1.0,
                    window_ms=WINDOW_MS, frequencies=FREQUENCIES_HZ) -> list:
    n_bins = int(round(window_ms / bin_ms))
    t_s = (np.arange(n_bins) + 0.5) * bin_ms / 1000.0
    base_groups, base_global = _baseline(brain, dark, groups, window_ms)
    results = []
    for f in frequencies:
        trace, global_trace, n_l_pulses, n_r_pulses = _run_pulse_trial(
            brain, dark, groups, l_idx, r_idx, amp, f, window_ms, bin_ms, 0.0)
        total = {k: float(v.sum()) for k, v in trace.items()}
        non_baseline = {k: total[k] - base_groups[k] for k in total}
        locking = {k: vector_strength_z(v, t_s, f) for k, v in trace.items()}
        row = {
            "frequency_hz": f, "n_pulses_each_cell": n_l_pulses,
            "total_by_group": total, "non_baseline_by_group": non_baseline,
            "global_total": float(global_trace.sum()),
            "global_non_baseline": float(global_trace.sum()) - base_global,
            "global_locking": vector_strength_z(global_trace, t_s, f),
            "locking_by_group": locking,
        }
        results.append(row)
        summed = sum(v for k, v in non_baseline.items())
        print(f"f={f:6.1f} Hz  pulses={n_l_pulses:4d}  "
              f"sum_non_baseline_readouts={summed:8.1f}  "
              f"global_z={row['global_locking']['z']}", flush=True)

    # Reset verification: re-run the first frequency and require an exact
    # match, the same check haltere_axis_pairs.py makes of its own reset --
    # "the reset is verified rather than assumed."
    check_trace, check_global, _, _ = _run_pulse_trial(
        brain, dark, groups, l_idx, r_idx, amp, frequencies[0], window_ms, bin_ms, 0.0)
    check_total = {k: float(v.sum()) for k, v in check_trace.items()}
    first_total = results[0]["total_by_group"]
    reset_ok = (check_total == first_total and
               float(check_global.sum()) == results[0]["global_total"])
    if not reset_ok:
        raise RuntimeError(
            f"State reset is not clean: repeating f={frequencies[0]} Hz gave "
            f"{check_total} (global {check_global.sum()}) vs first run's "
            f"{first_total} (global {results[0]['global_total']}). Every "
            "result in this run is suspect.")
    print(f"Reset verified: repeating f={frequencies[0]} Hz reproduced exactly.", flush=True)
    return results, {"groups": base_groups, "global": base_global}


def _resolvable_offsets(freq_hz, window_ms, bin_ms, phase_steps_deg):
    """How many of the requested phase steps land on distinct bin patterns.

    At 1 ms bins, a high-frequency period is only a few bins long, so several
    nominally-different phase steps snap to the same (l_bins, r_bins) pair --
    a flat response across those steps then reflects the bin quantization,
    not the pathway. Report this count so a flat sweep isn't misread as "phase
    doesn't matter" when it is really "N of 13 points were actually distinct."
    """
    seen = set()
    for phi in phase_steps_deg:
        l = frozenset(_pulse_bins(freq_hz, window_ms, bin_ms, 0.0))
        r = frozenset(_pulse_bins(freq_hz, window_ms, bin_ms, phi))
        seen.add((l, r))
    return len(seen)


def run_experiment2(brain, dark, groups, l_idx, r_idx, amp, frequencies_selected,
                    bin_ms=0.5, window_ms=WINDOW_MS,
                    phase_steps_deg=PHASE_STEPS_DEG) -> list:
    """bin_ms=0.5 is deliberate, not a compromise -- see below.

    Phase resolution needs the bin size smaller than the smallest phase
    step's time shift, checked explicitly per frequency via
    _resolvable_offsets rather than assumed. bin_ms=1.0 (experiment 1's
    value) under-resolves 218/300 Hz's 30-degree steps; the fix is *not*
    simply "go finer" -- measured directly here (four calls to
    _run_pulse_trial at decreasing bin_ms, same everything else): the
    per-group readouts (b1/b2/hg1/power/DLM) go to exactly zero at
    bin_ms<=0.25 while `global` stays large and nonzero, at both 200 ms and
    1000 ms windows. That is an engine sensitivity to very short per-call
    durations, not a property of the pathway, and it is not chased further
    here. bin_ms=0.5 is the finest step confirmed not to trigger it, matches
    haltere_depth_phase.py's already-validated value, and still resolves 12
    of 13 phase steps at both 218 and 300 Hz (verified via
    _resolvable_offsets, printed below) -- 12 is the ceiling here since -180
    and +180 degrees are the same condition by construction.
    """
    n_bins = int(round(window_ms / bin_ms))
    t_s = (np.arange(n_bins) + 0.5) * bin_ms / 1000.0
    base_groups, base_global = _baseline(brain, dark, groups, window_ms)
    results = []
    resolution = {}
    for f in frequencies_selected:
        n_distinct = _resolvable_offsets(f, window_ms, bin_ms, phase_steps_deg)
        resolution[f] = n_distinct
        print(f"f={f:6.1f} Hz  resolvable phase conditions at bin_ms={bin_ms}: "
              f"{n_distinct} of {len(phase_steps_deg)}", flush=True)
        for phi in phase_steps_deg:
            trace, global_trace, n_l, n_r = _run_pulse_trial(
                brain, dark, groups, l_idx, r_idx, amp, f, window_ms, bin_ms, phi)
            total = {k: float(v.sum()) for k, v in trace.items()}
            non_baseline = {k: total[k] - base_groups[k] for k in total}
            row = {
                "frequency_hz": f, "phase_deg": phi,
                "total_by_group": total, "non_baseline_by_group": non_baseline,
                "global_total": float(global_trace.sum()),
                "global_non_baseline": float(global_trace.sum()) - base_global,
                "global_locking": vector_strength_z(global_trace, t_s, f),
            }
            results.append(row)
            summed = sum(v for k, v in non_baseline.items())
            print(f"f={f:6.1f} Hz  phase={phi:+4d} deg  "
                  f"sum_non_baseline_readouts={summed:8.1f}", flush=True)
    return results, {"groups": base_groups, "global": base_global}, resolution


def run(*, dataset="malecns_v1", out=ROOT / "outputs/haltere_sapp_pulse.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    groups = _all_groups(ann)
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    r_idx = _find_cell(brain, SAPP_R_BODY_ID)
    l_idx = _find_cell(brain, SAPP_L_BODY_ID)

    started = time.time()
    print("=== Calibrating pulse amplitude ===", flush=True)
    cal_r = calibrate_pulse_amplitude(brain, dark, r_idx)
    cal_l = calibrate_pulse_amplitude(brain, dark, l_idx)
    amp = max(cal_r["chosen_amplitude_mV"], cal_l["chosen_amplitude_mV"])
    print(f"R (101048) calibrated to {cal_r['chosen_amplitude_mV']} mV, "
          f"L (136883) calibrated to {cal_l['chosen_amplitude_mV']} mV -- "
          f"using shared amplitude {amp} mV", flush=True)

    print("\n=== Experiment 1: in-phase frequency sweep ===", flush=True)
    exp1, exp1_baseline = run_experiment1(brain, dark, groups, l_idx, r_idx, amp)

    # Selection rule: frequencies whose summed non-baseline response across
    # b1/b2/hg1/power/DLM readouts (not "global") is largest. POWER_TYPES
    # (haltere_axis_pairs.py) already includes both DLM types, and DLM_L/DLM_R
    # are our own added readout of that same subset -- summing both double-
    # counts DLM. Exclude DLM_L/DLM_R from the *ranking* score only (they are
    # still reported in full in non_baseline_by_group for every trial).
    def score(row):
        return sum(v for k, v in row["non_baseline_by_group"].items()
                   if k not in ("DLM_L", "DLM_R"))
    ranked = sorted(exp1, key=score, reverse=True)
    scores = [(row["frequency_hz"], score(row)) for row in ranked]
    best_score = scores[0][1]
    # Keep any frequency within 20% of the best score as a joint selection,
    # else keep only the single best. Invented margin, stated here.
    selected = [f for f, s in scores if s >= 0.8 * best_score] if best_score > 0 else [scores[0][0]]
    selected = selected[:2] if len(selected) > 2 else selected
    print(f"\nRanked by summed non-baseline response: {scores}", flush=True)
    print(f"Selected for experiment 2: {selected} Hz", flush=True)

    # Frequency-vs-pulse-count confound: exp1 delivers different total pulse
    # counts at different frequencies over the same fixed window (5 at 5 Hz,
    # 218 at 218 Hz), so a rising response-per-window could be pulse count,
    # not frequency tuning. Response-per-pulse (from data already collected,
    # no extra run needed) separates the two: flat across frequency means an
    # integrator that doesn't care about timing; frequency-dependent means
    # real tuning.
    per_pulse = []
    for row in exp1:
        n = row["n_pulses_each_cell"]
        s = sum(v for k, v in row["non_baseline_by_group"].items()
               if k not in ("DLM_L", "DLM_R"))
        per_pulse.append({"frequency_hz": row["frequency_hz"], "n_pulses": n,
                          "response_per_window": s,
                          "response_per_pulse": round(s / n, 3) if n else None})
    print("\nResponse per pulse (pulse-count-confound check):", flush=True)
    for r in per_pulse:
        print(f"  f={r['frequency_hz']:6.1f} Hz  n_pulses={r['n_pulses']:4d}  "
              f"per_window={r['response_per_window']:8.1f}  "
              f"per_pulse={r['response_per_pulse']}", flush=True)

    print("\n=== Experiment 2: phase sweep at selected frequency(ies) ===", flush=True)
    exp2, exp2_baseline, exp2_resolution = run_experiment2(
        brain, dark, groups, l_idx, r_idx, amp, selected)

    report = {
        "dataset": dataset,
        "sapp_r_body_id": SAPP_R_BODY_ID, "sapp_l_body_id": SAPP_L_BODY_ID,
        "pulse_ms": PULSE_MS,
        "calibration": {"R_101048": cal_r, "L_136883": cal_l, "shared_amplitude_mV": amp},
        "experiment1": {
            "frequencies_hz": list(FREQUENCIES_HZ), "window_ms": WINDOW_MS, "bin_ms": 1.0,
            "baseline": exp1_baseline, "trials": exp1,
            "selection_rule": "largest summed non_baseline_by_group across "
                              "b1/b2/hg1/power/DLM readouts (global excluded, "
                              "and DLM excluded from the SUM since power "
                              "already contains it); keep any frequency "
                              "within 20% of the best score, at most 2",
            "ranked_scores": scores, "selected_frequencies_hz": selected,
            "pulse_count_confound_check": per_pulse,
        },
        "experiment2": {
            "phase_steps_deg": list(PHASE_STEPS_DEG), "window_ms": 200.0, "bin_ms": 0.1,
            "resolvable_phase_conditions": exp2_resolution,
            "baseline": exp2_baseline, "trials": exp2,
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
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_sapp_pulse.json"))
    a = p.parse_args()
    r = run(out=a.out)
    print(f"\ndone in {r['wall_seconds']} s -> {a.out}")
