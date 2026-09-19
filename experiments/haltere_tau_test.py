"""Is the first post-haltere synapse a simulation bottleneck or a real feature?

Measured: haltere afferents lock hard to a 218 Hz drive (z = 27.8) and their
direct targets do not (z = 0.27).  Two explanations, with different consequences.

*Simulation bottleneck.*  Every neuron in this model shares one 20 ms membrane
and 5 ms synaptic constant, whose corners are 8 Hz and 32 Hz.  Nothing at 218 Hz
can cross a synapse regardless of wiring, and the result says nothing about the
fly.

*Biological feature.*  The wiring itself discards the carrier -- convergence,
inhibition, or sheer fan-out averaging it away -- in which case a real fly could
not read a phase code through this pathway either.

The structure argues for the first: convergence onto hop-1 cells is modest
(median 4 afferents each), every synapse carries the same fixed 1.8 ms delay,
and hop 1 is 100% excitatory.  Afferents driven in phase therefore spike
synchronously and their inputs arrive synchronously, so summation preserves
phase.  Nothing structural is available to destroy it.

This tests that directly by lowering the time constants and asking whether
locking crosses the synapse.  Both constants scale together, keeping the 4:1
ratio, because a 5 ms synapse alone has a 32 Hz corner and would block 218 Hz
even with an instantaneous membrane.

**Total spike count is recorded at every setting as a positive control.**  A
faster leak means less temporal summation, so the network may simply fall
silent -- and a silent network gives the same null as a filtering one.  A drop
in locking is only interpretable while the pool is still firing.

Runs on the numba backend: the C++ and GPU kernels compile 20 ms / 5 ms in and
refuse a non-default value rather than ignoring it.  Results from a non-default
setting are **not** the audited Shiu-equivalent model and must be labelled.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# (tau_m, tau_s) in ms, 4:1 throughout. 20/5 is the reference model; 0.73 ms is
# the membrane constant whose corner sits exactly at a 218 Hz wingbeat.
TAUS = [(20.0, 5.0), (5.0, 1.25), (2.0, 0.5), (0.73, 0.18)]


def run(*, dataset="malecns_v1", taus=TAUS, freq=218.0, baseline=12.0, depth=4.0,
        bin_ms=0.5, duration_ms=500.0,
        out=ROOT / "outputs/haltere_tau_test.json") -> dict:
    from connectome_sim.engine import Brain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _readouts
    from experiments.haltere_mtf import null_distribution, vector_strength

    graph = str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz")
    n_bins = int(round(duration_ms / bin_ms))
    t_s = (np.arange(n_bins) + 0.5) * bin_ms / 1000.0
    results, started = [], time.time()

    for tau_m, tau_s in taus:
        brain = Brain(graph, tau_m=tau_m, tau_s=tau_s)
        ann = annotations(brain.ids)
        hal = np.flatnonzero((ann.subclass == "haltere").to_numpy()).astype(np.int32)
        h1 = set()
        for i in hal:
            h1 |= set(brain.post[brain.ptr[i]:brain.ptr[i + 1]].tolist())
        h1 = np.array(sorted(h1 - set(hal.tolist())), dtype=np.int32)
        motor = np.concatenate(list(_readouts(ann).values()))
        depths = {"0_afferents": hal, "1_direct_targets": h1, "3_wing_motor": motor}
        dark = np.zeros(len(brain.retina), np.float32)

        trace = {k: np.zeros(n_bins) for k in depths}
        for k in range(n_bins):
            drive = baseline + depth * np.sin(2 * np.pi * freq * t_s[k])
            c, _ = brain.step(dark, bin_ms, stimulation=(hal, float(drive)))
            for name, ix in depths.items():
                trace[name][k] = c[ix].sum()
        row = {"tau_m_ms": tau_m, "tau_s_ms": tau_s,
               "membrane_corner_hz": round(1 / (2 * np.pi * tau_m / 1000), 1),
               "reference_dynamics": brain.reference_dynamics, "by_depth": {}}
        for name, counts in trace.items():
            r = vector_strength(counts, t_s, freq)
            mu, sd, _ = null_distribution(counts, t_s, freq)
            row["by_depth"][name] = {
                "r": round(r, 5), "spikes": float(counts.sum()),
                "z": round((r - mu) / sd, 2) if sd else None}
        results.append(row)
        z = {k: v["z"] for k, v in row["by_depth"].items()}
        sp = {k: int(v["spikes"]) for k, v in row["by_depth"].items()}
        print(f"tau_m={tau_m:5.2f} corner={row['membrane_corner_hz']:6.1f}Hz  "
              f"z " + " ".join(f"{k.split('_')[0]}:{str(v):>6s}" for k, v in z.items()) +
              f"  | spikes " + " ".join(f"{v:6d}" for v in sp.values()), flush=True)

    report = {"dataset": dataset, "frequency_hz": freq, "baseline_mV": baseline,
              "depth_mV": depth, "duration_ms": duration_ms, "backend": "numba Brain",
              "warning": "non-default time constants are not the audited "
                         "Shiu-equivalent model",
              "settings": results, "wall_seconds": round(time.time() - started, 1)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration-ms", type=float, default=500.0)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_tau_test.json"))
    a = p.parse_args()
    r = run(duration_ms=a.duration_ms, out=a.out)
    print(f"\n{len(r['settings'])} settings in {r['wall_seconds']} s -> {a.out}")
