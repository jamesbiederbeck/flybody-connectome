"""Can two carriers the membrane cannot pass produce a beat that it can?

A wingbeat-frequency carrier is present in the haltere afferents (z = 27.8 at
218 Hz) and destroyed by the first synapse (z = 0.27).  But two carriers at
f1 and f2 have an envelope at |f1 - f2|, and a *slow* envelope would pass the
20 ms membrane easily.  That is a route by which a network of slow neurons could
read a fast signal -- and the mechanism a real fly would need, since its neurons
are slow relative to a 218 Hz wingbeat too.

The envelope is not free.  A linear sum of two sinusoids has no power at
|f1 - f2|; the beat only becomes a signal after a nonlinearity.  In this model
current sums linearly into the membrane, which then low-passes, and the spike
threshold comes last -- so *where* the two frequencies meet decides everything:

  same_population  both frequencies injected into the same cells, so they sum in
                   `drive[]` and meet the afferent's own spike threshold before
                   any synapse or filtering.  Prediction: beat appears.
  split_population one cluster at f1, another at f2 (the binaural arrangement).
                   They meet only at a shared downstream target, after two
                   stages of low-pass.  Prediction: no beat.

Both are run at frequencies inside the passband (5 and 7 Hz) as a positive
control -- if no beat appears *there*, the measurement is broken rather than the
mechanism absent -- and at wingbeat frequencies where the carriers cannot pass.

Vector strength is measured at the beat frequency |f1 - f2|, not at the carriers.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASELINE_MV = 12.0
# Half the single-tone depth each, so the two-tone sum spans the same range as
# the one-tone runs and amplitude cannot explain a difference.
TONE_MV = 2.0

PAIRS = [(5.0, 7.0), (218.0, 220.0), (218.0, 228.0), (218.0, 218.0)]


def run(*, dataset="malecns_v1", pairs=PAIRS, baseline=BASELINE_MV, tone=TONE_MV,
        bin_ms=0.5, duration_ms=2000.0,
        out=ROOT / "outputs/haltere_beat.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _readouts, _reset
    from experiments.haltere_mtf import null_distribution, vector_strength

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    motor = np.concatenate(list(_readouts(ann).values()))
    hal = np.flatnonzero((ann.subclass == "haltere").to_numpy()).astype(np.int32)
    side = ann.rootSide.to_numpy()
    left = hal[side[hal] == "L"]
    right = hal[side[hal] == "R"]

    h1 = set()
    for i in hal:
        h1 |= set(brain.post[brain.ptr[i]:brain.ptr[i + 1]].tolist())
    h1 = np.array(sorted(h1 - set(hal.tolist())), dtype=np.int32)
    depths = {"0_afferents": hal, "1_direct_targets": h1, "3_wing_motor": motor}

    # Duration is long: resolving a 2 Hz beat needs several of its cycles, not
    # several of the carrier's.
    n_bins = int(round(duration_ms / bin_ms))
    t_s = (np.arange(n_bins) + 0.5) * bin_ms / 1000.0
    dark = np.zeros(len(brain.retina), dtype=np.float32)
    results, started = [], time.time()

    for f1, f2 in pairs:
        beat = abs(f1 - f2)
        for mode in ("same_population", "split_population"):
            _reset(brain)
            trace = {k: np.zeros(n_bins) for k in depths}
            for k in range(n_bins):
                a = tone * np.sin(2 * np.pi * f1 * t_s[k])
                b = tone * np.sin(2 * np.pi * f2 * t_s[k])
                if mode == "same_population":
                    stim = [(hal, float(baseline + a + b))]
                else:
                    stim = [(left, float(baseline + 2 * a)),
                            (right, float(baseline + 2 * b))]
                c, _ = brain.step(dark, bin_ms, stimulation=stim)
                for name, ix in depths.items():
                    trace[name][k] = c[ix].sum()
            row = {"f1": f1, "f2": f2, "beat_hz": beat, "mode": mode, "by_depth": {}}
            for name, counts in trace.items():
                entry = {"spikes": float(counts.sum())}
                for label, freq in (("beat", beat), ("carrier_f1", f1)):
                    if freq <= 0:
                        continue
                    r = vector_strength(counts, t_s, freq)
                    mu, sd, _ = null_distribution(counts, t_s, freq)
                    entry[label] = {"r": round(r, 5),
                                    "z": round((r - mu) / sd, 2) if sd else None}
                row["by_depth"][name] = entry
            results.append(row)
            zb = {k: (v.get("beat") or {}).get("z") for k, v in row["by_depth"].items()}
            zc = {k: (v.get("carrier_f1") or {}).get("z") for k, v in row["by_depth"].items()}
            print(f"{f1:5.0f}/{f2:5.0f} beat={beat:5.1f} {mode:17s} "
                  f"beat_z " + " ".join(f"{k.split('_')[0]}:{str(v):>6s}" for k, v in zb.items()) +
                  f"  | carrier_z " + " ".join(f"{str(v):>6s}" for v in zc.values()), flush=True)

    report = {"dataset": dataset, "baseline_mV": baseline, "tone_mV": tone,
              "bin_ms": bin_ms, "duration_ms": duration_ms,
              "prediction": "same_population beats (mixing precedes the afferent "
                            "threshold); split_population does not (mixing happens "
                            "only after two low-pass stages)",
              "trials": results, "wall_seconds": round(time.time() - started, 1)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration-ms", type=float, default=2000.0)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_beat.json"))
    a = p.parse_args()
    r = run(duration_ms=a.duration_ms, out=a.out)
    print(f"\n{len(r['trials'])} trials in {r['wall_seconds']} s -> {a.out}")
