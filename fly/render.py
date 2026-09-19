"""Render a run to video, so the setup can be looked at rather than inferred.

Everything else in this repo reports numbers.  This renders the same loop
through MuJoCo's offscreen renderer: the external `scene_cam` for the body, and
optionally the two compound-eye cameras, which is also the quickest check that
the retina is pointed at anything.

    MUJOCO_GL=egl python -m fly.render --world flat --ms 200

Open loop by default -- wingbeat pattern generator only, no connectome -- because
the usual question here is a physics one ("does it fly", "do the wings beat")
that the brain contributes nothing to.  `--brain` runs `fly.play`'s full loop
instead, rendering from inside it rather than reimplementing it, at the cost of
loading a 25.6M-edge graph and running ~25x slower than real time.

Playback is heavily slowed.  At 25 fps a frame is taken every
`playback_speed / 25` seconds of simulation, so the default 0.005 puts about 23
frames in each 4.6 ms wingbeat -- fine for inspecting a stroke, far too many for
a whole fall.  `--playback-speed 0.04` gives ~3 frames per beat, which is what a
few hundred milliseconds of flight wants.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

WINGBEAT_HZ = 218.0


def render(*,
           world: str = "flat",
           ms: float = 200.0,
           medium: str = "air",
           wingbeat_hz: float = WINGBEAT_HZ,
           flap: bool = True,
           hover: bool = False,
           wing_pattern: str | None = None,
           eyes: bool = False,
           playback_speed: float = 0.005,
           camera_res: tuple[int, int] = (480, 640),
           out: Path | str = ROOT / "outputs/render/flight.mp4") -> dict:
    """Run open loop and write a video.  Returns a small trajectory report."""
    from flygym.rendering import Renderer

    from fly import body as body_mod
    from fly.body import SCENE_CAMERA
    from vendor.pattern_generators import (_FLY_CONTROL_TIMESTEP,
                                           WingBeatPatternGenerator)

    fly = body_mod.build(world=world, medium=medium)
    model, data = fly.model, fly.data
    if hover:
        # Gravity off, so the body stays near rest and the measured vertical
        # fluid force is lift alone.  Falling contaminates it badly: a descending
        # body sees an upward drag that `qfrc_passive` cannot be distinguished
        # from lift, and at terminal velocity that ratio tends to 1 no matter
        # what the wings are doing.
        model.opt.gravity[:] = 0.0

    cameras = [SCENE_CAMERA]
    if eyes:
        cameras += [f"{fly.name}/{s}_eye_cam_camera" for s in ("l", "r")]

    # The measured base pattern from the flybody figshare dataset, when given.
    # Without it the generator falls back to a bare sine that upstream's own
    # docstring calls "not a substitute for a realistic base wing pattern".
    wpg = WingBeatPatternGenerator(base_pattern_path=wing_pattern)
    wpg.reset(initial_phase=0.0)

    dt = float(model.opt.timestep)
    n = int(round(ms / 1000.0 / dt))
    # The WPG advances one control timestep (2e-4 s) per call against a 1e-4 s
    # physics step, so it is stepped every other step.  Calling it every step
    # flaps at ~436 Hz, which the position servos cannot track: achieved wing
    # amplitude collapses from 2.8 rad to 1.2 rad while the command is unchanged.
    wpg_every = max(1, int(round(_FLY_CONTROL_TIMESTEP / dt)))
    thorax = _thorax_id(model, fly.name)
    stroke = np.zeros(6)
    z, fz = [], []

    out = Path(out)
    with Renderer(model, cameras, camera_res=camera_res,
                  playback_speed=playback_speed) as renderer:
        for i in range(n):
            if flap and i % wpg_every == 0:
                stroke = wpg.step(ctrl_freq=wingbeat_hz)
            data.ctrl[fly.wing_actuator_ids] = stroke if flap else 0.0
            fly.sim.step()
            z.append(float(data.xpos[thorax, 2]))
            if not fly.tethered:
                # MuJoCo accumulates fluid forces in qfrc_passive; dof 2 is the
                # root freejoint's world z.  This is the lift measurement, and
                # unlike the trajectory it is unaffected by hitting the ground.
                fz.append(float(data.qfrc_passive[2]))
            renderer.render_as_needed(data)
        renderer.save_video(out if len(cameras) == 1 else out.parent)

    z = np.asarray(z)
    t = np.arange(n) * dt
    g = -float(model.opt.gravity[2])
    free_fall = z[0] - 0.5 * g * t**2
    # `g` is zero in hover mode, so weight is computed from the real constant.
    weight = float(model.body_subtreemass[0]) * 9810.0
    report = {
        "video": str(out if len(cameras) == 1 else out.parent),
        "world": world,
        "medium": medium,
        "flap": flap,
        "sim_ms": ms,
        "hover": hover,
        "wing_pattern": wing_pattern or "bare sine (no base pattern)",
        "thorax_z_mm": [round(z[0], 3), round(z[-1], 3)],
        # Tethered this is meaningless (the thorax is welded); free it is the
        # whole question.  A fly that is flying sits above the parabola.
        "free_fall_z_mm": round(float(free_fall[-1]), 3),
        "above_free_fall_mm": round(float(z[-1] - free_fall[-1]), 3),
    }
    if fz:
        # Mean over whole wingbeats only; a partial beat biases the mean by more
        # than the mean itself, since peak force is ~4x body weight either way.
        beats = int(len(fz) // (1.0 / wingbeat_hz / dt))
        keep = int(beats * (1.0 / wingbeat_hz / dt)) or len(fz)
        report["lift_over_weight"] = round(float(np.mean(fz[:keep]) / weight), 4)
        report["peak_vertical_force_over_weight"] = round(
            float(np.abs(fz[:keep]).max() / weight), 2)
    return report


def render_brain(*,
                 ticks: int = 10,
                 world: str = "flat",
                 source: str = "motor",
                 haltere_gain: float = 5.0,
                 brain_hz: float = 30.0,
                 frozen_vision: bool = False,
                 eyes: bool = False,
                 playback_speed: float = 0.04,
                 camera_res: tuple[int, int] = (480, 640),
                 out: Path | str = ROOT / "outputs/render/brain.mp4") -> dict:
    """Render `fly.play`'s closed loop: eyes and halteres -> connectome -> wings.

    The renderer is handed to `play.run` as a factory rather than the loop being
    duplicated here, so what ends up on screen is the same code path the JSON
    reports come from.  Defaults are the one condition that currently does
    anything -- free flight, motor readout, haltere current -- see README,
    "What free flight did fix".
    """
    from flygym.rendering import Renderer

    from fly.body import SCENE_CAMERA
    from fly import play

    cameras = [SCENE_CAMERA]
    if eyes:
        cameras += [f"flybody/{s}_eye_cam_camera" for s in ("l", "r")]

    out = Path(out)
    holder = {}

    def make_renderer(model):
        holder["r"] = Renderer(model, cameras, camera_res=camera_res,
                               playback_speed=playback_speed)
        return holder["r"]

    report = play.run(ticks=ticks, world=world, source=source,
                      haltere_gain=haltere_gain, brain_hz=brain_hz,
                      frozen_vision=frozen_vision, make_renderer=make_renderer)
    renderer = holder["r"]
    try:
        renderer.save_video(out if len(cameras) == 1 else out.parent)
    finally:
        renderer.close()
    report["video"] = str(out if len(cameras) == 1 else out.parent)
    return report


def _thorax_id(model, name: str) -> int:
    import mujoco as mj

    return mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, f"{name}/c_thorax")


def main() -> None:
    import json

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world", choices=("tethered", "flat"), default="flat")
    p.add_argument("--medium", choices=("air", "flygym"), default="air")
    p.add_argument("--ms", type=float, default=200.0)
    p.add_argument("--wingbeat-hz", type=float, default=WINGBEAT_HZ)
    p.add_argument("--wing-pattern", default=None,
                   help="path to a measured base wing pattern (timesteps, 3)")
    p.add_argument("--hover", action="store_true",
                   help="gravity off; measure lift alone, uncontaminated by fall drag")
    p.add_argument("--no-flap", action="store_true",
                   help="control condition: hold the wings still")
    p.add_argument("--eyes", action="store_true",
                   help="also render both compound-eye cameras")
    p.add_argument("--playback-speed", type=float, default=None,
                   help="default 0.005 open loop (a stroke), 0.04 with --brain "
                        "(a few hundred ms of flight)")
    p.add_argument("--brain", action="store_true",
                   help="run fly.play's closed loop instead of open loop")
    p.add_argument("--ticks", type=int, default=10, help="--brain only")
    p.add_argument("--source", choices=("descending", "motor"), default="motor",
                   help="--brain only")
    p.add_argument("--haltere-gain", type=float, default=5.0, help="--brain only")
    p.add_argument("--frozen-vision", action="store_true", help="--brain only")
    p.add_argument("--out", default=None)
    a = p.parse_args()
    if a.brain:
        out = a.out or str(ROOT / "outputs/render/brain.mp4")
        speed = 0.04 if a.playback_speed is None else a.playback_speed
        print(json.dumps(render_brain(ticks=a.ticks, world=a.world, source=a.source,
                                      haltere_gain=a.haltere_gain,
                                      frozen_vision=a.frozen_vision, eyes=a.eyes,
                                      playback_speed=speed, out=out), indent=2))
        return
    a.out = a.out or str(ROOT / "outputs/render/flight.mp4")
    a.playback_speed = 0.005 if a.playback_speed is None else a.playback_speed
    print(json.dumps(render(world=a.world, medium=a.medium, ms=a.ms,
                            wingbeat_hz=a.wingbeat_hz, flap=not a.no_flap, hover=a.hover, wing_pattern=a.wing_pattern,
                            eyes=a.eyes, playback_speed=a.playback_speed,
                            out=a.out), indent=2))


if __name__ == "__main__":
    main()
