"""Structural assumptions about FlyGym's FlyBody.

FlyGym flags its FlyBody support as experimental ("the API may change in future
releases, and not all features available for the default NeuroMechFly model are
currently supported"), so every structural fact `fly/body.py` relies on is
asserted here.  A FlyGym bump that changes the model should fail loudly rather
than silently changing the physics.

These need flygym, mujoco and a one-time ~140 MB asset download, so they skip
cleanly when it is unavailable.
"""
import os

# Must precede the mujoco import: mujoco selects its GL backend at import time,
# and without this it picks GLFW and dies headless when it cannot open DISPLAY.
os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("flygym")
pytest.importorskip("mujoco")

from fly import body as body_mod  # noqa: E402


@pytest.fixture(scope="module")
def fly():
    return body_mod.build()


def test_actuator_and_joint_counts(fly):
    assert fly.model.nu == body_mod.EXPECTED_NU
    assert fly.model.nq == body_mod.EXPECTED_NQ


def test_all_six_wing_actuators_resolve(fly):
    assert fly.wing_actuator_ids.shape == (6,)
    assert len(set(fly.wing_actuator_ids.tolist())) == 6
    assert (fly.wing_actuator_ids >= 0).all()


def test_both_eye_cameras_exist(fly):
    assert len(fly.eye_camera_ids) == 2
    assert all(i >= 0 for i in fly.eye_camera_ids)


def test_wing_fluid_geoms_are_restored(fly):
    import mujoco as mj
    names = [mj.mj_id2name(fly.model, mj.mjtObj.mjOBJ_GEOM, i)
             for i in range(fly.model.ngeom)]
    wing = {n.split("/")[-1] for n in names if n and "wing" in n}
    # FlyGym ships only brown+membrane; wing_fluid.py re-adds fluid+inertial.
    assert {"l_wing_fluid", "r_wing_fluid",
            "l_wing_inertial", "r_wing_inertial"} <= wing


def test_fluid_medium_is_air_in_millimetre_units(fly):
    """FlyGym ships the medium unconverted; `body.build` corrects it.

    `mujoco_globals.yaml` converts gravity cm->mm and every body density with it,
    but leaves `option/density` at 0.00128 and `option/viscosity` at 0.000185 --
    air in g/cm^3 and g/(cm.s), which in FlyGym's millimetre model is 1000x and
    10x too much.  Shipped, the fly flaps in something denser than water.
    """
    assert fly.model.opt.density == pytest.approx(body_mod.AIR_DENSITY_MM)
    assert fly.model.opt.viscosity == pytest.approx(body_mod.AIR_VISCOSITY_MM)


def test_flygym_medium_option_keeps_the_shipped_values():
    """The A/B control.  If this ever equals the corrected value, FlyGym fixed it
    upstream and `medium="air"` has become a no-op."""
    f = body_mod.build(medium="flygym")
    assert f.model.opt.density == pytest.approx(0.00128)
    assert f.model.opt.viscosity == pytest.approx(0.000185)


def test_free_world_has_a_root_freejoint_and_the_tethered_one_does_not(fly):
    import mujoco as mj

    def freejoints(model):
        return [j for j in range(model.njnt)
                if model.jnt_type[j] == mj.mjtJoint.mjJNT_FREE]

    assert freejoints(fly.model) == []
    assert fly.tethered
    free = body_mod.build(world="flat")
    assert len(freejoints(free.model)) == 1
    assert not free.tethered
    # The freejoint adds 7 qpos / 6 qvel on top of the tethered model.
    assert free.model.nq == body_mod.EXPECTED_NQ + 7


def test_scene_camera_exists_in_both_worlds(fly):
    import mujoco as mj

    for f in (fly, body_mod.build(world="flat")):
        assert mj.mj_name2id(f.model, mj.mjtObj.mjOBJ_CAMERA,
                             body_mod.SCENE_CAMERA) >= 0


def test_per_geom_ellipsoid_fluid_is_off_by_default(fly):
    """Upstream flybody does not enable it; neither do we without asking."""
    gf = fly.model.geom_fluid.reshape(fly.model.ngeom, -1)
    assert int((gf.sum(axis=1) != 0).sum()) == 0


def test_ellipsoid_fluid_flag_enables_exactly_the_two_wing_geoms():
    f = body_mod.build(ellipsoid_fluid=True)
    gf = f.model.geom_fluid.reshape(f.model.ngeom, -1)
    assert int((gf.sum(axis=1) != 0).sum()) == 2


def test_simulation_steps(fly):
    t0 = fly.data.time
    fly.step(50)
    assert fly.data.time > t0
    assert np.all(np.isfinite(fly.data.qpos))


def test_ommatidia_readout_shape(fly):
    v = fly.ommatidia()
    assert v.shape == (2, body_mod.EXPECTED_OMMATIDIA, 2)
    assert np.isfinite(v).all()
