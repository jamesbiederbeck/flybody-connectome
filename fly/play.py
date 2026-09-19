"""Headless run: eyes -> connectome -> wing muscles -> tethered flight.

    ommatidia -> achromatic -> receptors -> Brain.step -> FlightControls.decode
              -> WPG + steering offsets -> wing actuators -> physics

Two rates, deliberately decoupled.  `Brain.dt` is pinned to 0.1 ms and the fly's
physics runs at 1e-4 s, but the connectome has 166,700 neurons and 25.6M edges,
so stepping it per physics step is not affordable.  The brain runs at a
Doom-like ~30 Hz and its decoded action is held constant across the intervening
physics steps, while the wingbeat pattern generator runs at physics rate.  The
fly therefore beats its wings at ~218 Hz under a steering command updated 30
times a second -- which is roughly the right separation of timescales anyway.

Needs `outputs/connectome_sim/<dataset>/graph.npz`; build it with
`python -m connectome_sim.prepare` from this repo's root.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run(ticks: int = 300,
        dataset: str = "malecns_v1",
        *,
        brain_hz: float = 30.0,
        haltere_gain: float = 0.0,
        frozen_vision: bool = False,
        source: str = "descending",
        seed: int = 0) -> dict:
    """Run the tethered loop and return a JSON-able report.

    Args:
        ticks: Number of brain steps.
        dataset: Graph dataset name under `outputs/connectome_sim/`.
        brain_hz: Brain update rate; the decoded action is held between updates.
        haltere_gain: Current per rad/s injected into haltere afferents.  0
            disables proprioceptive feedback entirely.
        frozen_vision: Freeze the retinal input at the first frame.  This is the
            control condition -- see README, "Is vision reaching the wings?".
        source: "descending" decodes DNp20/DNpe017, the only cells visual input
            reaches in this connectome. "motor" decodes the wing motor neurons,
            which stay silent unless `haltere_gain` is injecting current.
        seed: Unused by the physics (tethered and deterministic); recorded so
            reports are comparable.
    """
    from connectome_sim.native import NativeBrain

    from fly import body as body_mod
    from fly import circuit, retina_map
    from fly.controls import FlightControls
    from vendor.pattern_generators import WingBeatPatternGenerator

    graph = ROOT / "outputs/connectome_sim" / dataset / "graph.npz"
    if not graph.exists():
        raise FileNotFoundError(
            f"No graph at {graph}. Run 'python -m connectome_sim.prepare' first."
        )

    brain = NativeBrain(str(graph))
    fly = body_mod.build()

    if source == "descending":
        controls = FlightControls.from_descending(brain)
    else:
        controls = FlightControls(circuit.power_muscle_readouts(brain),
                                  circuit.steering_muscle_readouts(brain),
                                  source="motor")
    halteres = circuit.haltere_afferents(brain) if haltere_gain else None

    mapping = _build_receptor_map(brain, fly, graph)
    wpg = WingBeatPatternGenerator()
    wpg.reset(initial_phase=0.0)

    duration_ms = 1000.0 / brain_hz
    physics_dt = float(fly.model.opt.timestep)
    substeps = max(1, int(round((duration_ms / 1000.0) / physics_dt)))

    frozen = None
    history = {"wingbeat_hz": [], "offsets": [], "spikes": []}
    started = time.time()

    for _ in range(ticks):
        readouts = fly.ommatidia()
        if frozen_vision:
            frozen = readouts if frozen is None else frozen
            readouts = frozen
        light = mapping(readouts)

        stim = None
        if halteres is not None:
            gyro = _thorax_gyro(fly)
            stim = circuit.proprioceptive_stimulation(halteres, gyro, gain=haltere_gain)

        counts, _ = brain.step(light, duration_ms, stimulation=stim)
        action = controls.decode(counts, duration_ms / 1000.0)

        history["wingbeat_hz"].append(action["wingbeat_hz"])
        history["offsets"].append(action["wing_offsets"].copy())
        history["spikes"].append(int(counts.sum()))

        for _ in range(substeps):
            stroke = wpg.step(ctrl_freq=action["wingbeat_hz"])
            fly.data.ctrl[fly.wing_actuator_ids] = stroke + action["wing_offsets"]
            fly.sim.step()

    offsets = np.asarray(history["offsets"])
    wall = time.time() - started
    sim_seconds = ticks * substeps * physics_dt
    return {
        "dataset": dataset,
        "readout_source": source,
        "ticks": ticks,
        "seed": seed,
        "frozen_vision": frozen_vision,
        "haltere_gain": haltere_gain,
        "brain_hz": brain_hz,
        "physics_substeps_per_brain_step": substeps,
        "receptors_driven": int(mapping.n_driven),
        "receptors_unmatched": int(mapping.n_unmatched),
        "registration": mapping.manifest,
        "total_spikes": int(sum(history["spikes"])),
        "mean_spikes_per_step": float(np.mean(history["spikes"])),
        "wingbeat_hz_mean": float(np.mean(history["wingbeat_hz"])),
        "wingbeat_hz_range": [float(np.min(history["wingbeat_hz"])),
                              float(np.max(history["wingbeat_hz"]))],
        # The steering readout: how asymmetric the wing command was. A loop with
        # no visual drive sits near zero.
        "steering_asymmetry_mean": float(np.abs(offsets[:, :3]).mean()),
        "steering_asymmetry_max": float(np.abs(offsets[:, :3]).max()),
        "sim_seconds": round(sim_seconds, 4),
        "wall_seconds": round(wall, 2),
        "realtime_ratio": round(sim_seconds / wall, 4) if wall else None,
    }


class _ReceptorMap:
    """Scatters per-ommatidium readings onto the connectome's receptors."""

    def __init__(self, gather, n_receptors, n_driven, n_unmatched, manifest):
        self._gather = gather
        self._n = n_receptors
        self.n_driven = n_driven
        self.n_unmatched = n_unmatched
        self.manifest = manifest

    def __call__(self, readouts):
        from fly import retina_map

        flat = retina_map.achromatic(np.asarray(readouts))  # (2, n_ommatidia)
        light = np.zeros(self._n, dtype=np.float32)
        for eye, (receptors, ommatidia) in self._gather.items():
            if len(receptors):
                light[receptors] = flat[eye][ommatidia]
        return light


def _build_receptor_map(brain, fly, graph_path) -> _ReceptorMap:
    """Register each eye's columns onto FlyGym's lattice, once, at startup."""
    from connectome_sim.physiology.common import annotations
    from flygym.vision.retina import Retina

    from fly import retina_map

    # Brain only keeps the arrays its kernel needs; 'hexes' is written by
    # prepare.py for exactly this purpose, so read it from the graph directly.
    with np.load(graph_path) as g:
        if "hexes" not in g:
            raise KeyError(
                f"{graph_path} has no 'hexes' array; rebuild it with "
                "'python -m connectome_sim.prepare'."
            )
        graph_hexes = g["hexes"]
    xy = retina_map.hex_to_cartesian(graph_hexes)
    sides = annotations(brain.ids).rootSide.to_numpy()[brain.retina]
    ommatidia = retina_map.ommatidia_centroids(Retina().ommatidia_id_map)

    gather, manifest, unmatched = {}, {}, 0
    for eye, label in enumerate(("L", "R")):
        mask = sides == label
        if not mask.any():
            gather[eye] = (np.array([], dtype=np.int64), np.array([], dtype=np.int64))
            continue
        columns, inverse = np.unique(xy[mask], axis=0, return_inverse=True)
        reg = retina_map.register(columns, ommatidia)
        manifest[label] = reg.as_manifest()
        unmatched += reg.unmatched
        per_receptor = reg.assignment[inverse]
        keep = per_receptor >= 0
        receptor_rows = np.flatnonzero(mask)[keep]
        gather[eye] = (receptor_rows.astype(np.int64),
                       per_receptor[keep].astype(np.int64))

    driven = sum(len(v[0]) for v in gather.values())
    return _ReceptorMap(gather, len(brain.retina), driven,
                        len(brain.retina) - driven, manifest)


def _thorax_gyro(fly) -> np.ndarray:
    """Angular velocity of the thorax, in its own frame, rad/s.

    Uses `mj_objectVelocity` rather than slicing `qvel`, because `TetheredWorld`
    has **no freejoint** -- `qvel[3:6]` there is not the body's angular velocity
    at all, it is three mouthpart joints.  This function works with or without a
    root freejoint, so it stays correct when the fly is untethered.

    Tethered, the thorax is welded and this reads ~0, so the haltere drive is
    inert.  That is correct and worth knowing: the haltere pathway only carries a
    signal once the body can actually rotate.

    Note this is *body* angular velocity, not haltere state.  The model's
    halteres do not beat and carry no sensors, so nothing here measures a real
    Coriolis force -- see README, "Are the halteres wired up?".
    """
    import mujoco as mj

    body_id = mj.mj_name2id(fly.model, mj.mjtObj.mjOBJ_BODY, f"{fly.name}/c_thorax")
    if body_id < 0:
        return np.zeros(3)
    vel = np.zeros(6)
    # flg_local=1 -> the body's own frame; rotational part comes first.
    mj.mj_objectVelocity(fly.model, fly.data, mj.mjtObj.mjOBJ_BODY, body_id, vel, 1)
    return np.asarray(vel[:3], dtype=float)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ticks", type=int, default=300)
    p.add_argument("--dataset", default="malecns_v1")
    p.add_argument("--brain-hz", type=float, default=30.0)
    p.add_argument("--haltere-gain", type=float, default=0.0)
    p.add_argument("--frozen-vision", action="store_true",
                   help="control condition: freeze the retinal input")
    p.add_argument("--source", choices=("descending", "motor"), default="descending",
                   help="which cells to decode; 'motor' needs --haltere-gain")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    print(json.dumps(run(ticks=args.ticks, dataset=args.dataset,
                         brain_hz=args.brain_hz, haltere_gain=args.haltere_gain,
                         frozen_vision=args.frozen_vision, source=args.source,
                         seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
