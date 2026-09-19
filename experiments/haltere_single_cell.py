"""Is "cluster" the wrong unit of analysis for this connectome?

Three separate results have landed on single cells rather than the populations
they belong to:

  * SNpp12 is two cells, and one of them (946174) produces 611 motor spikes
    alone at 8 mV while the other produces 3.
  * SNpp23's antiphase drive fails to cancel at the afferents, which requires
    its three left and three right cells to differ in efficacy.
  * In Johnston's organ, JO-FD's 8 cells beat size-matched random 19-cell draws
    outright, while the 475-cell wind/gravity pool is indistinguishable from
    random.

If potency is generally carried by a few cells, then every cluster-level null in
this log may be a single-cell effect averaged into invisibility, and the pair
and phase designs have been testing the wrong objects.

This drives all 205 haltere afferents one at a time and records the wing motor
response of each.  Two things fall out: the distribution of per-cell potency,
and for each type, how much of its measured cluster response one cell accounts
for.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run(*, dataset="malecns_v1", currents=(8.0, 14.0, 20.0), duration_ms=500.0,
        out=ROOT / "outputs/haltere_single_cell.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _readouts, _reset

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    groups = _readouts(ann)
    hal = np.flatnonzero((ann.subclass == "haltere").to_numpy())
    types = ann.type.astype(str).to_numpy(dtype="U64")
    side = ann.rootSide.to_numpy()
    outdeg = np.diff(brain.ptr)
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    # Unstimulated baseline, so spontaneous motor activity is not read as a
    # response from a cell that did nothing.
    _reset(brain)
    base_counts, _ = brain.step(dark, duration_ms, None)
    base = {k: int(base_counts[v].sum()) for k, v in groups.items()}

    cells, started = [], time.time()
    for n, i in enumerate(hal):
        idx = np.array([i], dtype=np.int32)
        row = {"graph_index": int(i), "body_id": str(brain.ids[i]),
               "type": types[i], "side": str(side[i]),
               "out_degree": int(outdeg[i]), "by_current": {}}
        for mv in currents:
            _reset(brain)
            c, _ = brain.step(dark, duration_ms, stimulation=(idx, mv))
            resp = {k: int(c[v].sum()) - base[k] for k, v in groups.items()}
            row["by_current"][str(mv)] = {"total": sum(resp.values()), **resp}
        cells.append(row)
        if n % 25 == 0 or row["by_current"][str(currents[-1])]["total"] > 100:
            tot = {mv: row["by_current"][mv]["total"] for mv in row["by_current"]}
            print(f"[{n:3d}/{len(hal)}] {row['type']:12s} {row['side']} "
                  f"{row['body_id']:>10s} outdeg={row['out_degree']:4d}  " +
                  " ".join(f"{mv}:{v:6d}" for mv, v in tot.items()), flush=True)

    report = {"dataset": dataset, "duration_ms": duration_ms,
              "currents_mV": list(currents), "unstimulated_baseline": base,
              "cells": cells, "wall_seconds": round(time.time() - started, 1)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration-ms", type=float, default=500.0)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_single_cell.json"))
    a = p.parse_args()
    r = run(duration_ms=a.duration_ms, out=a.out)
    print(f"\n{len(r['cells'])} cells in {r['wall_seconds']} s -> {a.out}")
