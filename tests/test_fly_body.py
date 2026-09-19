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

import numpy as np
import pytest

pytest.importorskip("flygym")
pytest.importorskip("mujoco")
os.environ.setdefault("MUJOCO_GL", "egl")

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


def test_global_fluid_medium_matches_upstream_flybody(fly):
    assert fly.model.opt.density == pytest.approx(0.00128)
    assert fly.model.opt.viscosity == pytest.approx(0.000185)


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
