"""Compile flybody's fruitfly MJCF and save it as a compact .mjb the Android
writhe lab can load directly with mj_loadModel, plus a JSON map of actuator
and joint names to their ctrl/qpos/qvel indices (Java addresses them by name,
never by MuJoCo's raw integer indices, which can silently reorder across
model edits).

Deliberately loads the raw MJCF, not through dm_control's task/composer
wrapper -- none of the RL/task scaffolding (WingBeatPatternGenerator, the
trained policy, imitation rewards) is used by the writhe lab, which drives
actuators directly from the connectome's MotorRegions readouts instead. The
ellipsoid fluid model is left at whatever the raw asset sets (off, per
upstream's own default) -- it's a wing-lift term, irrelevant to a body
struggling under gravity, and costs step time for no visual benefit here.

The desktop MuJoCo version used here MUST match the one the Android build
links against (see androsophila/README.md's "Writhe lab" section) -- .mjb is
a version-specific binary serialization, not a portable format.
"""
import json
import sys
from pathlib import Path

import mujoco

FLYBODY_ROOT = Path.home() / 'code/playground/drosophila/flybody'
FRUITFLY_XML = FLYBODY_ROOT / 'flybody/fruitfly/assets/fruitfly.xml'


def export(out_dir=None):
    out = Path(out_dir) if out_dir else Path(__file__).resolve().parents[1] / 'outputs/mujoco/android'
    out.mkdir(parents=True, exist_ok=True)

    # The bare fruitfly.xml has no ground plane at all -- upstream's own
    # arenas (ball.py, hills.py) add one, but those pull in the full
    # dm_control composer stack this export deliberately bypasses. Add a
    # plain plane geom to the worldbody directly via MjSpec instead, sized
    # and placed from the model's own resting-pose geometry so it works
    # regardless of this model's length unit (previous investigation found
    # a live cm/mm confusion in this project -- see WritheRenderer's
    # scale-derived camera for the same defensiveness).
    base = mujoco.MjModel.from_xml_path(str(FRUITFLY_XML))
    base_data = mujoco.MjData(base)
    mujoco.mj_forward(base, base_data)
    min_z = min(base_data.geom_xpos[i][2] - base.geom_rbound[i] for i in range(base.ngeom))
    max_z = max(base_data.geom_xpos[i][2] + base.geom_rbound[i] for i in range(base.ngeom))
    span = max_z - min_z

    spec = mujoco.MjSpec.from_file(str(FRUITFLY_XML))
    floor = spec.worldbody.add_geom()
    floor.type = mujoco.mjtGeom.mjGEOM_PLANE
    floor.size = [span * 40 + 0.01, span * 40 + 0.01, 0.01]
    floor.pos = [0, 0, min_z]
    floor.rgba = [0.3, 0.3, 0.3, 1]
    model = spec.compile()

    mjb_path = out / 'fruitfly.mjb'
    mujoco.mj_saveModel(model, str(mjb_path), None)

    actuators = {
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): {
            'index': i,
            'ctrlrange': [float(model.actuator_ctrlrange[i][0]), float(model.actuator_ctrlrange[i][1])],
        }
        for i in range(model.nu)
    }
    joints = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i): i
              for i in range(model.njnt)}
    free_joint = next((name for name, i in joints.items()
                        if model.jnt_type[i] == mujoco.mjtJoint.mjJNT_FREE), None)

    manifest = {
        'mujoco_version': mujoco.__version__,
        'nbody': model.nbody, 'njnt': model.njnt, 'nu': model.nu,
        'nq': model.nq, 'nv': model.nv, 'timestep': model.opt.timestep,
        'actuators': actuators,
        'joints': joints,
        'free_joint': free_joint,
        'source_xml': str(FRUITFLY_XML),
        # Resting-pose geometry (before the floor was added), for the two
        # writhe-lab starting scenarios: 'floor' spawns just above floor_z,
        # 'flight' drops from well above max_z. Unitless here deliberately --
        # whatever length unit this model turns out to use, these are
        # expressed in that same unit.
        'floor_z': min_z,
        'body_top_z': max_z,
        'body_span': span,
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True))

    print(f'wrote {mjb_path} ({mjb_path.stat().st_size} bytes)')
    print(f'wrote {out / "manifest.json"}')
    print(f'nbody={model.nbody} njnt={model.njnt} nu={model.nu} '
          f'timestep={model.opt.timestep} free_joint={free_joint}')


if __name__ == '__main__':
    export(sys.argv[1] if len(sys.argv) > 1 else None)
