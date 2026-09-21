"""Fine-grained census of the SApp-triggered saturated state.

Runs the same SApp_pair_30mV protocol as connectome-lab/latch-characterization.json
(drive 30mV/500ms on SApp_R body_id 101048 + SApp_L body_id 136883, 500ms dark
settle, 1000ms post-drive-removed window) but reports at `class`, `entryNerve`,
`exitNerve` and `somaNeuromere` resolution instead of the coarser
`superclass`/`subclass` used previously -- those columns are measured
annotations, not an inferred grouping, unlike the ROI-name-prefix census this
session also tried and mostly failed to get coverage on.

Baseline is a dark, unstimulated network -- already shown elsewhere (an
extended 12.5s zero-stimulation run) to sit at a flat ~1.6 Hz/cell floor with
zero drift toward saturation. So "baseline 0.000 Hz" for a class below is not
evidence that class is suppressed *by* the latch; it means the whole network's
resting state is close to silent, and the latch is a rise from that floor, not
a shift between two nonzero levels.
"""
import json
import numpy as np
from connectome_sim.native import NativeBrain
from connectome_sim.report import population_report

GRAPH = "/home/victor/code/playground/flybody-connectome/outputs/connectome_sim/malecns_v1/graph.npz"
OUT = "/home/victor/code/playground/connectome-lab/latch-full-census.json"


def main():
    brain = NativeBrain(GRAPH)
    ids = brain.ids
    ids_str = ids.astype(str)
    sapp_idx = [int(np.flatnonzero(ids_str == "101048")[0]),
                int(np.flatnonzero(ids_str == "136883")[0])]

    drive_mv, drive_ms, settle_ms, post_ms = 30.0, 500.0, 500.0, 1000.0
    n = brain.n
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    def dark_step(duration_ms, stimulation=None):
        return brain.step(dark, duration_ms, stimulation=stimulation)

    baseline_counts = np.zeros(n, dtype=np.int64)
    c, _ = dark_step(settle_ms)
    baseline_counts += np.asarray(c)

    stim = (np.asarray(sapp_idx, dtype=np.int64), np.full(2, drive_mv, dtype=np.float32))
    dark_step(drive_ms, stimulation=stim)

    latched_counts = np.zeros(n, dtype=np.int64)
    c, _ = dark_step(post_ms)
    latched_counts += np.asarray(c)

    out = {"protocol": {"drive_mv": drive_mv, "drive_ms": drive_ms,
                        "settle_ms": settle_ms, "post_ms": post_ms}}
    for by in ["class", "entryNerve", "exitNerve", "somaNeuromere"]:
        out[f"by_{by}"] = {
            "baseline": population_report(ids, baseline_counts, settle_ms, by=by),
            "latched": population_report(ids, latched_counts, post_ms, by=by),
        }

    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
