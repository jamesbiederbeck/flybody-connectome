"""The wing servo resonates inside the wingbeat band. Does fixing it give lift?

FlyGym drives the wings with position actuators at kp 300/200/100 against a
joint damping of 0.05, which puts the yaw dof's natural frequency at 235 Hz --
7% from the 218 Hz wingbeat, with Q ~ 4.  The wing therefore sweeps 2.26x
further than commanded, so the prescribed stroke never actually happens and no
base wing pattern can matter until it does.  (Upstream flybody uses gain 18 with
damping 0.00777 and stiffness 0.01, a different regime entirely.)

A real fly *is* a resonant system at wingbeat frequency, so resonance here is
not wrong in itself.  What is wrong is commanding kinematics through a resonant
servo and getting different kinematics out.  Either the servo tracks and the
pattern means something, or it does not and the pattern is decoration.

Sweeps damping and gain, reporting for each: the achieved/commanded amplitude
ratio per dof, and the lift that results.  Lift is measured exactly as
`fly/render.py --hover` does -- gravity zeroed, `qfrc_passive[2]` averaged over
whole wingbeats -- so the numbers are comparable to the -0.018 body weights
already on record.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WINGBEAT_HZ = 218.0
PATTERN = ROOT / "assets/wing_pattern_fmech.npy"


def run(*, damping_scales=(1.0, 2.0, 4.0, 8.0), gain_scales=(1.0, 3.0, 10.0),
        ms=300.0, pattern=str(PATTERN),
        out=ROOT / "outputs/wing_gain_sweep.json") -> dict:
    import mujoco as mj

    from fly import body as body_mod
    from vendor.pattern_generators import (_FLY_CONTROL_TIMESTEP,
                                           WingBeatPatternGenerator)

    results, started = [], time.time()
    for gs in gain_scales:
        for ds in damping_scales:
            fly = body_mod.build(world="flat")
            m, d = fly.model, fly.data
            m.opt.gravity[:] = 0.0   # lift alone, as in render.py --hover
            jids = [mj.mj_name2id(m, mj.mjtObj.mjOBJ_JOINT, f"flybody/{a}")
                    for a in body_mod.WING_ACTUATORS]
            dofs = [m.jnt_dofadr[j] for j in jids]
            qadr = [m.jnt_qposadr[j] for j in jids]
            m.actuator_gainprm[fly.wing_actuator_ids, 0] *= gs
            # A position actuator's bias term must track its gain or the servo
            # stops being a servo: biasprm[1] is -kp.
            m.actuator_biasprm[fly.wing_actuator_ids, 1] *= gs
            for dd in dofs:
                m.dof_damping[dd] *= ds
            kp = m.actuator_gainprm[fly.wing_actuator_ids[0], 0]
            fn = np.sqrt((kp + m.jnt_stiffness[jids[0]]) / m.dof_M0[dofs[0]]) / (2 * np.pi)

            wpg = WingBeatPatternGenerator(base_pattern_path=pattern)
            wpg.reset(initial_phase=0.0)
            dt = float(m.opt.timestep)
            every = max(1, int(round(_FLY_CONTROL_TIMESTEP / dt)))
            n = int(round(ms / 1000.0 / dt))
            settle = n // 3
            stroke = np.zeros(6)
            cmd, ach, fz = [], [], []
            for i in range(n):
                if i % every == 0:
                    stroke = wpg.step(ctrl_freq=WINGBEAT_HZ)
                d.ctrl[fly.wing_actuator_ids] = stroke
                fly.sim.step()
                if i >= settle:
                    cmd.append(stroke.copy())
                    ach.append(d.qpos[qadr].copy())
                    fz.append(float(d.qfrc_passive[2]))
            cmd, ach, fz = np.array(cmd), np.array(ach), np.array(fz)
            beat = 1.0 / WINGBEAT_HZ / dt
            keep = int(int(len(fz) // beat) * beat) or len(fz)
            weight = float(m.body_subtreemass[0]) * 9810.0
            ratios = [float((np.ptp(ach[:, k])) / np.ptp(cmd[:, k])) if np.ptp(cmd[:, k]) else 0.0
                      for k in range(3)]
            row = {"gain_scale": gs, "damping_scale": ds,
                   "kp_yaw": float(kp), "damping": float(m.dof_damping[dofs[0]]),
                   "f_n_yaw_hz": round(float(fn), 1),
                   "track_ratio": {n_: round(r, 3) for n_, r in
                                   zip(("yaw", "roll", "pitch"), ratios)},
                   "lift_over_weight": round(float(np.mean(fz[:keep]) / weight), 4),
                   "peak_over_weight": round(float(np.abs(fz[:keep]).max() / weight), 2)}
            results.append(row)
            print(f"gain x{gs:4.1f} damp x{ds:4.1f}  kp={kp:6.0f} f_n={fn:6.1f}Hz  "
                  f"track yaw={ratios[0]:5.2f} roll={ratios[1]:5.2f} pitch={ratios[2]:5.2f}  "
                  f"lift={row['lift_over_weight']:+.4f}", flush=True)

    report = {"wingbeat_hz": WINGBEAT_HZ, "pattern": pattern, "ms": ms,
              "baseline": "kp 300/200/100, damping 0.05 -> yaw f_n 235 Hz, "
                          "track 2.26, lift -0.016",
              "settings": results, "wall_seconds": round(time.time() - started, 1)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ms", type=float, default=300.0)
    p.add_argument("--out", default=str(ROOT / "outputs/wing_gain_sweep.json"))
    a = p.parse_args()
    r = run(ms=a.ms, out=a.out)
    best = max(r["settings"], key=lambda s: s["lift_over_weight"])
    print(f"\nbest lift: {best['lift_over_weight']:+.4f} at gain x{best['gain_scale']} "
          f"damping x{best['damping_scale']} (track yaw {best['track_ratio']['yaw']})")
