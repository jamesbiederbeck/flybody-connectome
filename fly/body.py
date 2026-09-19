"""Build the FlyBody model, tethered, with eye cameras and wing aerodynamics.

The body comes from FlyGym (NeuroMechFly v2), which ships TuragaLab's flybody
model already parsed and rigged into millimetre units, with the compound-eye
cameras placed and a published ommatidia sampling pipeline attached.  That saves
this project from maintaining a second model checkout and from inventing its own
retinal projection.

Tethered on purpose.  `TetheredWorld` fixes the thorax in space while the wings
still beat, which is the standard *Drosophila* flight-neuroscience preparation:
wing kinematics and the forces they produce are measurable directly, and the fly
cannot fall out of the sky while the decoder is still uncalibrated.  Free flight
comes later.

FlyGym's FlyBody support is flagged experimental by its own authors ("the API may
change in future releases, and not all features available for the default
NeuroMechFly model are currently supported"), so the FlyGym version is pinned and
`test_fly_body.py` re-checks every structural assumption made here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fly.wing_fluid import add_wing_fluid_geoms

# Wing actuator order, as the compiled model reports it.  Left before right, and
# yaw/roll/pitch within each -- matching FlyGym's actuators.yaml gain groups
# (300/200/100), which preserve upstream flybody's 3:2:1 yaw:roll:pitch ratio.
WING_ACTUATORS = (
    "c_thorax-l_wing-yaw",
    "c_thorax-l_wing-roll",
    "c_thorax-l_wing-pitch",
    "c_thorax-r_wing-yaw",
    "c_thorax-r_wing-roll",
    "c_thorax-r_wing-pitch",
)

# Structural facts asserted by the tests, so a FlyGym bump that changes the model
# fails loudly here instead of silently changing the physics.
EXPECTED_NU = 110
EXPECTED_NQ = 102
EXPECTED_OMMATIDIA = 721


@dataclass
class TetheredFly:
    """A compiled, tethered FlyBody with vision and named actuator indices."""

    fly: object
    world: object
    sim: object
    wing_actuator_ids: np.ndarray
    eye_camera_ids: tuple[int, ...]

    @property
    def model(self):
        return self.sim.mj_model

    @property
    def data(self):
        return self.sim.mj_data

    @property
    def name(self) -> str:
        return self.fly.name

    def ommatidia(self) -> np.ndarray:
        """Per-ommatidium readings, shape (2, n_ommatidia, 2).

        Axis 0 is left then right eye.  Axis 2 is the yellow- and pale-type
        channels: exactly one is populated per ommatidium, the other reads zero,
        per FlyGym's `pale_type_mask`.  See `fly.retina_map` for how this reaches
        the connectome's receptors -- do not just take `[..., 0]`.
        """
        return self.sim.get_ommatidia_readouts(self.fly.name)

    def step(self, n: int = 1) -> None:
        for _ in range(n):
            self.sim.step()


def build(
    *,
    name: str = "flybody",
    wing_fluid: bool = True,
    ellipsoid_fluid: bool = False,
    spawn_height_mm: float = 0.8,
) -> TetheredFly:
    """Construct and compile the tethered fly.

    The call sequence follows FlyGym's own
    `scripts/launch_flybody_interactive_viewer.py`, which is the canonical
    example for this model.

    Args:
        name: Fly name; becomes the prefix on every compiled MuJoCo element.
        wing_fluid: Re-add the wing fluid/inertial geoms FlyGym drops.  Off only
            for A/B testing what their absence does.
        ellipsoid_fluid: Enable MuJoCo's per-geom ellipsoid fluid model on those
            geoms.  Upstream flybody does not; see `fly.wing_fluid`.
        spawn_height_mm: Tether height above the origin.
    """
    import mujoco as mj
    from flygym import Simulation
    from flygym.compose import ActuatorType, KinematicPosePreset
    from flygym.compose.fly import FlyBody
    from flygym.compose.world.tethered_world import TetheredWorld
    from flygym.flybody.anatomy_flybody import (
        FlyBodyActuatedDOFPreset,
        FlyBodyAxisOrder,
        FlyBodyJointPreset,
        FlyBodySkeleton,
    )
    from flygym.utils.math import Rotation3D

    fly = FlyBody(name=name)
    skeleton = FlyBodySkeleton(
        joint_preset=FlyBodyJointPreset.ALL_BIOLOGICAL,
        axis_order=FlyBodyAxisOrder.YAW_ROLL_PITCH,
    )
    fly.add_joints(skeleton, KinematicPosePreset.FLYBODY_NEUTRAL)
    fly.add_actuators(
        skeleton.get_actuated_dofs_from_preset(FlyBodyActuatedDOFPreset.ALL),
        ActuatorType.POSITION,
    )
    fly.add_tendons()
    fly.add_tendon_actuators()
    fly.add_vision()

    if wing_fluid:
        add_wing_fluid_geoms(fly, ellipsoid_fluid=ellipsoid_fluid)

    world = TetheredWorld()
    # The freejoint's neutral rotation must be given as a quaternion; FlyGym
    # rejects euler here.
    world.add_fly(fly, (0, 0, spawn_height_mm), Rotation3D("quat", (1, 0, 0, 0)))

    sim = Simulation(world)
    model = sim.mj_model

    wing_ids = np.array(
        [_actuator_id(model, f"{name}/{a}") for a in WING_ACTUATORS], dtype=np.int32
    )
    eye_ids = tuple(
        mj.mj_name2id(model, mj.mjtObj.mjOBJ_CAMERA, f"{name}/{c}_eye_cam_camera")
        for c in ("l", "r")
    )
    return TetheredFly(fly=fly, world=world, sim=sim,
                       wing_actuator_ids=wing_ids, eye_camera_ids=eye_ids)


def _actuator_id(model, prefix: str) -> int:
    """Resolve an actuator by name, tolerating FlyGym's `-position` suffix."""
    import mujoco as mj

    for candidate in (prefix, f"{prefix}-position", f"{prefix}-motor"):
        i = mj.mj_name2id(model, mj.mjtObj.mjOBJ_ACTUATOR, candidate)
        if i >= 0:
            return i
    raise ValueError(f"No actuator matching {prefix!r} in the compiled model.")
