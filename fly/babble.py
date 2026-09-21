"""Motor babble: stand the fly on the ground, inject random sensory current,
and record what the body does, one row per brain tick.

This is a data-collection run, not an experiment with a hypothesis. Every
class in the sibling `flappy-haltere` project drove one hand-picked population
and asked whether the output moved. That found a wall: vision reaches the
descending neurons and stops, and the only motor drive that works is current
injected into haltere afferents. Rather than guess the next population, this
drives *all* of them at random and writes the input/output pairs to disk, so
the question "which inputs move which outputs" becomes something to fit rather
than something to guess.

**Everything injected here is host-side current added to `drive[]` before the
audited kernel runs.** It is not transduction. A real chordotonal organ encodes
strain with spike timing; this adds a scalar to a cell's input current because
that cell is labelled `chordotonal organ` in the reconstruction. The labels are
the connectome's; the currents are ours.

The fly stands on a flat ground plane rather than being tethered, because a
tethered thorax is welded and its angular velocity is identically zero, which
makes the whole proprioceptive pathway inert. On the ground the body can
actually move, so the recorded outputs include kinematics that the inputs could
in principle explain.

Sparse random drive, not all-channels-on: each tick every channel is
independently active with probability `--density`, amplitude uniform on
[0, --max-current]. Sparsity is what makes the channels separable afterwards;
driving all 19 every tick would leave their contributions collinear.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# Sensory superclasses in this reconstruction. Subclass within these is the
# input channel: 'haltere', 'chordotonal organ', 'auditory', and so on.
SENSORY_SUPERCLASSES = ("vnc_sensory", "cb_sensory", "ol_sensory", "sensory_ascending")


def input_channels(brain, minimum_cells: int = 32):
    """One channel per sensory subclass, as (name, graph indices)."""
    from connectome_sim.physiology.common import annotations
    a = annotations(brain.ids)
    sensory = a.superclass.isin(SENSORY_SUPERCLASSES).to_numpy()
    out = []
    for name in sorted(set(a.subclass[sensory].dropna())):
        idx = np.flatnonzero(sensory & (a.subclass == name).to_numpy()).astype(np.int32)
        if len(idx) >= minimum_cells:
            out.append((str(name), idx))
    if not out:
        raise ValueError("No sensory channels found in this graph")
    return out


def output_groups(brain):
    """Populations to record per tick. Motor first, since that is the thing a
    body command has to come out of; descending next, because that is where the
    sibling projects measured the signal actually stopping."""
    from connectome_sim.physiology.common import annotations
    from fly import circuit
    a = annotations(brain.ids)
    t = a.type.fillna("")
    groups = {
        "dlm": np.flatnonzero(t.isin(circuit.DLM_TYPES).to_numpy()),
        "steering_mn": np.flatnonzero(t.isin(circuit.STEERING_TYPES).to_numpy()),
        "wing_muscle": np.flatnonzero((a.subclass == "wm").to_numpy()),
        "vnc_motor": np.flatnonzero((a.superclass == "vnc_motor").to_numpy()),
        "descending": np.flatnonzero((a.superclass == "descending_neuron").to_numpy()),
        "dnp20": np.flatnonzero((t == circuit.DESCENDING_STEERING_TYPE).to_numpy()),
        "dnpe017": np.flatnonzero((t == circuit.DESCENDING_DRIVE_TYPE).to_numpy()),
        "ascending": np.flatnonzero((a.superclass == "ascending_neuron").to_numpy()),
    }
    return {k: v.astype(np.int32) for k, v in groups.items() if len(v)}


def body_state(fly) -> dict:
    """Thorax pose and velocity plus whole-body summaries, in model units."""
    import mujoco as mj
    d, m = fly.data, fly.model
    body = mj.mj_name2id(m, mj.mjtObj.mjOBJ_BODY, f"{fly.name}/thorax")
    if body < 0:  # name scheme differs between worlds; fall back to the root
        body = 1
    return {
        "thorax_xyz": np.asarray(d.xpos[body], float).copy(),
        "thorax_quat": np.asarray(d.xquat[body], float).copy(),
        "thorax_linvel": np.asarray(d.cvel[body][3:], float).copy(),
        "thorax_angvel": np.asarray(d.cvel[body][:3], float).copy(),
        "qpos_norm": float(np.linalg.norm(d.qpos)),
        "qvel_norm": float(np.linalg.norm(d.qvel)),
        "contact_count": int(d.ncon),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticks", type=int, default=2000, help="brain steps to record")
    p.add_argument("--settle-ticks", type=int, default=60,
                   help="physics-only steps before recording, to let the fly rest on the ground")
    p.add_argument("--dataset", default="malecns_v1")
    p.add_argument("--brain-hz", type=float, default=30.0)
    p.add_argument("--spawn-height-mm", type=float, default=2.0,
                   help="spawn just above the plane and drop, so it settles rather than falls")
    p.add_argument("--density", type=float, default=0.3,
                   help="probability a given channel is driven on a given tick")
    p.add_argument("--max-current", type=float, default=12.0,
                   help="upper bound of the uniform amplitude draw; E-SIGN in the "
                        "sibling repo puts the DLM response peak near 8")
    p.add_argument("--min-cells", type=int, default=32)
    p.add_argument("--seed", type=int, default=20260919)
    p.add_argument("--out", default=str(ROOT / "outputs/babble/run.npz"))
    args = p.parse_args()

    from connectome_sim.native import NativeBrain
    from fly import body as body_mod
    from fly import retina_map  # noqa: F401  (imported for the mapping builder)
    from fly.controls import FlightControls
    from fly.play import _build_receptor_map
    from vendor.pattern_generators import _FLY_CONTROL_TIMESTEP, WingBeatPatternGenerator

    graph = ROOT / "outputs/connectome_sim" / args.dataset / "graph.npz"
    if not graph.exists():
        raise FileNotFoundError(f"No graph at {graph}. Run 'python -m connectome_sim.prepare'.")

    brain = NativeBrain(str(graph))
    fly = body_mod.build(world="flat", spawn_height_mm=args.spawn_height_mm)
    controls = FlightControls.from_descending(brain)
    channels = input_channels(brain, args.min_cells)
    groups = output_groups(brain)
    mapping = _build_receptor_map(brain, fly, graph)

    physics_dt = float(fly.model.opt.timestep)
    duration_ms = 1000.0 / args.brain_hz
    substeps = max(1, int(round((duration_ms / 1000.0) / physics_dt)))
    wpg = WingBeatPatternGenerator()
    wpg.reset(initial_phase=0.0)
    wpg_every = max(1, int(round(_FLY_CONTROL_TIMESTEP / physics_dt)))
    stroke = np.zeros(len(fly.wing_actuator_ids))

    # Let it fall the last fraction of a millimetre and come to rest before any
    # row is written, so tick 0 is a standing fly rather than one in mid-air.
    for _ in range(args.settle_ticks * substeps):
        fly.step()
    settled = body_state(fly)

    rng = np.random.default_rng(args.seed)
    names = [n for n, _ in channels]
    inputs = np.zeros((args.ticks, len(channels)), np.float32)
    outputs = np.zeros((args.ticks, len(groups)), np.int64)
    active = np.zeros((args.ticks, len(groups)), np.int64)
    network = np.zeros(args.ticks, np.int64)
    pose = np.zeros((args.ticks, 13), np.float64)
    contacts = np.zeros(args.ticks, np.int64)
    # The decoded command is an output too: it is what the recorded spikes
    # actually did to the body, and it is cheaper to fit against than raw pose.
    wingbeat = np.zeros(args.ticks, np.float64)
    offsets = None
    started = time.time()

    for tick in range(args.ticks):
        amps = rng.uniform(0.0, args.max_current, len(channels))
        amps *= rng.random(len(channels)) < args.density
        inputs[tick] = amps
        stim = [(idx, float(a)) for (_, idx), a in zip(channels, amps) if a > 0]

        light = mapping(fly.ommatidia())
        counts, _ = brain.step(light, duration_ms, stimulation=stim or None)
        counts = np.asarray(counts)
        network[tick] = int(counts.sum())
        for j, (_, idx) in enumerate(groups.items()):
            outputs[tick, j] = int(counts[idx].sum())
            active[tick, j] = int((counts[idx] > 0).sum())

        action = controls.decode(counts, duration_ms / 1000.0)
        wingbeat[tick] = action["wingbeat_hz"]
        if offsets is None:
            offsets = np.zeros((args.ticks, len(action["wing_offsets"])), np.float64)
        offsets[tick] = action["wing_offsets"]

        # Same loop shape as fly.play: the pattern generator keeps the wings
        # beating and the decoded command sets frequency and asymmetry on top.
        for s in range(substeps):
            if s % wpg_every == 0:
                stroke = wpg.step(ctrl_freq=action["wingbeat_hz"])
            fly.data.ctrl[fly.wing_actuator_ids] = stroke + action["wing_offsets"]
            fly.sim.step()

        st = body_state(fly)
        pose[tick] = np.concatenate([st["thorax_xyz"], st["thorax_quat"],
                                     st["thorax_linvel"], st["thorax_angvel"]])
        contacts[tick] = st["contact_count"]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "experiment": "babble",
        "dataset": args.dataset,
        "world": "flat",
        "spawn_height_mm": args.spawn_height_mm,
        "settle_ticks": args.settle_ticks,
        "ticks": args.ticks,
        "brain_hz": args.brain_hz,
        "physics_dt": physics_dt,
        "substeps_per_tick": substeps,
        "density": args.density,
        "max_current": args.max_current,
        "seed": args.seed,
        "input_channels": [{"name": n, "cells": int(len(i))} for n, i in channels],
        "output_groups": [{"name": n, "cells": int(len(i))} for n, i in groups.items()],
        "pose_columns": ["x", "y", "z", "qw", "qx", "qy", "qz",
                         "vx", "vy", "vz", "wx", "wy", "wz"],
        "settled_state": {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                          for k, v in settled.items()},
        "stimulation_is_engineered": (
            "Host-side current added to drive[] before the kernel runs, selected by "
            "the reconstruction's own subclass labels. Not a transduction model."),
        "wingbeat_hz_range": [float(wingbeat.min()), float(wingbeat.max())],
        "wall_seconds": round(time.time() - started, 1),
    }
    np.savez_compressed(out, inputs=inputs, outputs=outputs, active_cells=active,
                        network_spikes=network, pose=pose, contacts=contacts,
                        wingbeat_hz=wingbeat, wing_offsets=offsets,
                        input_names=np.array(names),
                        output_names=np.array(list(groups)))
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({**meta, "out": str(out),
                      "mean_network_spikes": float(network.mean()),
                      "dlm_total": int(outputs[:, list(groups).index("dlm")].sum())
                      if "dlm" in groups else None}, indent=2))


if __name__ == "__main__":
    main()
