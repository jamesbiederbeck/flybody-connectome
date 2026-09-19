"""Where does a 218 Hz modulation die on the way to the wing muscles?

The motor pool shows nothing at 218 Hz (`haltere_mtf.py`), which was predicted
from the 8 Hz corner and is not in itself informative -- "absent at the output"
does not say whether the signal was never there, died at the first synapse, or
survived most of the way.  This reads out at four depths instead of one:

    stimulated afferents -> hop-1 targets -> hop-2 targets -> wing motor pool

Modulation must be present in the afferents by construction, so depth 0 is a
built-in positive control: if it is absent there, the drive itself is not
working and nothing downstream means anything.  Where it falls to chance is the
answer, and it is also the actionable one -- those are the cells that would need
a faster membrane constant for a phase code to survive.

Every cluster is run at 10 Hz as well as 218 Hz.  A cluster-level null at 218 Hz
is uninterpretable on its own, because single clusters showed nothing even at
10 Hz where the pathway demonstrably follows: too few cells to modulate the pool
detectably.  The 10 Hz run says whether that cluster can move the readout at all.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASELINE_MV = 12.0
DEPTH_MV = 4.0
PHASES = {"in_phase": 0.0, "antiphase": np.pi}


def run(*, dataset="malecns_v1", frequencies=(10.0, 218.0), baseline=BASELINE_MV,
        depth=DEPTH_MV, bin_ms=0.5, duration_ms=1000.0,
        out=ROOT / "outputs/haltere_depth_phase.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _clusters, _readouts, _reset
    from experiments.haltere_mtf import null_distribution, vector_strength

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    motor = np.concatenate(list(_readouts(ann).values()))
    side = ann.rootSide.to_numpy()
    hal = np.flatnonzero((ann.subclass == "haltere").to_numpy())
    clusters = _clusters(ann)
    types = ann.type.astype(str).to_numpy(dtype="U64")

    # Bilateral pairs. SApp is added explicitly: _clusters excludes it as the
    # undifferentiated bulk, but at 75/73 cells it is by far the largest group
    # and so has the best chance of a detectable cluster-level modulation.
    sapp = np.flatnonzero((types == "SApp") & (ann.subclass == "haltere").to_numpy())
    pairs = {
        "pooled_all": (hal[side[hal] == "L"].astype(np.int32),
                       hal[side[hal] == "R"].astype(np.int32)),
        "SApp": (sapp[side[sapp] == "L"].astype(np.int32),
                 sapp[side[sapp] == "R"].astype(np.int32)),
        "SNpp12": clusters["SNpp12"], "SNpp23": clusters["SNpp23"],
        "SNpp20": clusters["SNpp20"],  # silent at DC: a negative control
    }

    n_bins = int(round(duration_ms / bin_ms))
    t_s = (np.arange(n_bins) + 0.5) * bin_ms / 1000.0
    dark = np.zeros(len(brain.retina), dtype=np.float32)
    results, started = [], time.time()

    for pair_name, (a_idx, b_idx) in pairs.items():
        stim_set = np.concatenate([a_idx, b_idx])
        h1 = set()
        for i in stim_set:
            h1 |= set(brain.post[brain.ptr[i]:brain.ptr[i + 1]].tolist())
        h1 -= set(stim_set.tolist())
        h2 = set()
        for i in h1:
            h2 |= set(brain.post[brain.ptr[i]:brain.ptr[i + 1]].tolist())
        h2 -= h1 | set(stim_set.tolist())
        depths = {"0_stimulated": stim_set,
                  "1_direct_targets": np.array(sorted(h1), dtype=np.int32),
                  "2_second_order": np.array(sorted(h2), dtype=np.int32),
                  "3_wing_motor": motor}

        for f in frequencies:
            for phase_name, phi in PHASES.items():
                _reset(brain)
                trace = {k: np.zeros(n_bins) for k in depths}
                for k in range(n_bins):
                    wa = baseline + depth * np.sin(2 * np.pi * f * t_s[k])
                    wb = baseline + depth * np.sin(2 * np.pi * f * t_s[k] + phi)
                    c, _ = brain.step(dark, bin_ms, stimulation=[
                        (a_idx, float(wa)), (b_idx, float(wb))])
                    for name, ix in depths.items():
                        trace[name][k] = c[ix].sum()
                row = {"pair": pair_name, "frequency_hz": f, "phase": phase_name,
                       "cells_per_depth": {k: int(len(v)) for k, v in depths.items()},
                       "by_depth": {}}
                for name, counts in trace.items():
                    r = vector_strength(counts, t_s, f)
                    mu, sd, _ = null_distribution(counts, t_s, f)
                    row["by_depth"][name] = {
                        "r": round(r, 5), "spikes": float(counts.sum()),
                        "z": round((r - mu) / sd, 2) if sd else None}
                results.append(row)
                z = {k: v["z"] for k, v in row["by_depth"].items()}
                print(f"{pair_name:11s} {f:6.0f}Hz {phase_name:10s} " +
                      " ".join(f"{k.split('_')[0]}:{str(v):>6s}" for k, v in z.items()),
                      flush=True)

    report = {"dataset": dataset, "baseline_mV": baseline, "depth_mV": depth,
              "bin_ms": bin_ms, "duration_ms": duration_ms,
              "note": "depth 0 is a built-in positive control; modulation is "
                      "present in the stimulated cells by construction",
              "trials": results, "wall_seconds": round(time.time() - started, 1)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frequencies", type=float, nargs="+", default=[10.0, 218.0])
    p.add_argument("--duration-ms", type=float, default=1000.0)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_depth_phase.json"))
    a = p.parse_args()
    r = run(frequencies=a.frequencies, duration_ms=a.duration_ms, out=a.out)
    print(f"\n{len(r['trials'])} trials in {r['wall_seconds']} s -> {a.out}")
