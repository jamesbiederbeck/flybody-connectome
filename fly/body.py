"""Build the FlyBody model, tethered or free, with eye cameras and wing aerodynamics.

The body comes from FlyGym (NeuroMechFly v2), which ships TuragaLab's flybody
model already parsed and rigged into millimetre units, with the compound-eye
cameras placed and a published ommatidia sampling pipeline attached.  That saves
this project from maintaining a second model checkout and from inventing its own
retinal projection.

Tethered by default.  `TetheredWorld` fixes the thorax in space while the wings
still beat, which is the standard *Drosophila* flight-neuroscience preparation:
wing kinematics and the forces they produce are measurable directly, and the fly
cannot fall out of the sky while the decoder is still uncalibrated.
`world="flat"` gives the free-flight alternative -- an infinite checkered ground
plane, a root freejoint, and gravity -- for measuring whether the body actually
generates lift.

**FlyGym's fluid medium is in the wrong units, and this module corrects it.**
`assets/model/flybody/mujoco_globals.yaml` converts gravity from the upstream
cm-unit XML to mm (its own comment says so: "-981 cm/s^2 x10 -> mm") and the
rigging file converts every body density (0.713 g/cm^3 -> 7.13e-4 g/mm^3), but
`option/density` and `option/viscosity` were left at their cm values.  0.00128
g/cm^3 is air; 0.00128 g/mm^3 is 1280 kg/m^3, denser than water, and 1.85e-4 is
10x air's viscosity in g/(mm.s).  The fly is otherwise correct -- 1.0 mg, 1.4 mm
wing -- so as shipped it flaps in a liquid.  `medium="air"` (the default) sets
1.28e-6 and 1.85e-5; `medium="flygym"` keeps the shipped values for A/B.

FlyGym's FlyBody support is flagged experimental by its own authors ("the API may
change in future releases, and not all features available for the default
NeuroMechFly model are currently supported"), so the FlyGym version is pinned and
`test_fly_body.py` re-checks every structural assumption made here.
"""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

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


# Fluid medium in FlyGym's mm-g-s units: dry air at 20 C.
AIR_DENSITY_MM = 1.28e-6      # g/mm^3   (1.28 kg/m^3)
AIR_VISCOSITY_MM = 1.85e-5    # g/(mm.s) (1.85e-5 Pa.s)


@dataclass
class FlySim:
    """A compiled FlyBody with vision and named actuator indices."""

    fly: object
    world: object
    sim: object
    wing_actuator_ids: np.ndarray
    eye_camera_ids: tuple[int, ...]
    tethered: bool = True
    swatter_mocap: int = -1

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
    world: str = "tethered",
    medium: str = "air",
    wing_fluid: bool = True,
    ellipsoid_fluid: bool = False,
    spawn_height_mm: float | None = None,
    scene_camera: bool = True,
    swatter: bool = False,
    swatter_start_mm: tuple[float, float, float] = (0.0, 0.0, 60.0),
) -> FlySim:
    """Construct and compile the tethered fly.

    The call sequence follows FlyGym's own
    `scripts/launch_flybody_interactive_viewer.py`, which is the canonical
    example for this model.

    Args:
        name: Fly name; becomes the prefix on every compiled MuJoCo element.
        world: "tethered" (thorax welded, no freejoint) or "flat" (free flight
            over an infinite ground plane, with a root freejoint).
        medium: "air" corrects FlyGym's unconverted fluid globals to mm units;
            "flygym" keeps them as shipped, which is a 1000x too dense medium.
            See the module docstring.
        wing_fluid: Re-add the wing fluid/inertial geoms FlyGym drops.  Off only
            for A/B testing what their absence does.
        ellipsoid_fluid: Enable MuJoCo's per-geom ellipsoid fluid model on those
            geoms.  Upstream flybody does not, and it blows the integrator up
            within 3 ms here; see `fly.wing_fluid`.
        spawn_height_mm: Height above the origin.  Defaults to 0.8 mm tethered
            (the tether point) and 60 mm free (about 110 ms of fall).
        scene_camera: Add an external camera tracking the thorax, so
            `fly.render` has something to look through.  The eye cameras are
            always present.
        swatter: Add a fly swatter as a mocap body, from `assets/Fly Swatter.STL`
            (157 x 91 x 9.5 mm, which is a real swatter against a 3 mm fly).
            Mocap means its pose is written directly rather than simulated, so
            an approach trajectory is prescribed by the caller and nothing about
            the swatter's own dynamics enters the result.  It collides with the
            fly, so an approach that is not stopped will actually hit it.
        swatter_start_mm: Where the swatter sits before the caller moves it.
    """
    if world not in ("tethered", "flat"):
        raise ValueError(f"Unknown world: {world!r}")
    if medium not in ("air", "flygym"):
        raise ValueError(f"Unknown medium: {medium!r}")
    import mujoco as mj
    from flygym import Simulation
    from flygym.compose import ActuatorType, KinematicPosePreset
    from flygym.compose.fly import FlyBody
    from flygym.compose.world.flat_ground import FlatGroundWorld
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

    tethered = world == "tethered"
    if spawn_height_mm is None:
        spawn_height_mm = 0.8 if tethered else 60.0
    if tethered:
        scene, kwargs = TetheredWorld(), {}
    else:
        # Each fly class has its own contact-bodies enum; the base world's default
        # belongs to NeuroMechFly and is rejected for a FlyBody, so name it.
        scene = FlatGroundWorld()
        kwargs = {"bodysegs_with_ground_contact": "legs_thorax_abdomen_head"}
    # The freejoint's neutral rotation must be given as a quaternion; FlyGym
    # rejects euler here.
    scene.add_fly(fly, (0, 0, spawn_height_mm), Rotation3D("quat", (1, 0, 0, 0)), **kwargs)
    if swatter:
        _add_swatter(scene, swatter_start_mm)
    if scene_camera:
        _add_scene_camera(scene, name, tethered)
    world = scene

    sim = Simulation(world)
    model = sim.mj_model
    if medium == "air":
        model.opt.density = AIR_DENSITY_MM
        model.opt.viscosity = AIR_VISCOSITY_MM

    if swatter:
        # Resolve once here; the caller needs the mocap index every step and
        # mj_name2id on a hot loop is wasteful.
        body_id = mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, SWATTER_BODY)
        swatter_mocap = int(model.body_mocapid[body_id]) if body_id >= 0 else -1
    else:
        swatter_mocap = -1

    wing_ids = np.array(
        [_actuator_id(model, f"{name}/{a}") for a in WING_ACTUATORS], dtype=np.int32
    )
    eye_ids = tuple(
        mj.mj_name2id(model, mj.mjtObj.mjOBJ_CAMERA, f"{name}/{c}_eye_cam_camera")
        for c in ("l", "r")
    )
    return FlySim(fly=fly, world=world, sim=sim, wing_actuator_ids=wing_ids,
                  eye_camera_ids=eye_ids, tethered=tethered,
                  swatter_mocap=swatter_mocap)


# Name of the external camera added by `scene_camera=True`.
SCENE_CAMERA = "scene_cam"
SWATTER_BODY = "swatter"
SWATTER_MESH = Path(__file__).resolve().parents[1] / "assets/Fly Swatter.STL"


def _add_swatter(scene, start_mm) -> None:
    """Add the swatter as a mocap body with a mesh geom.

    Mocap, not a free body: the point of the experiment is a *prescribed*
    approach, so the trajectory is the independent variable and the swatter's
    own mass and dynamics stay out of it.  The mesh's origin is one corner of
    its bounding box, so the geom is offset to sit centred over the mocap point.
    """
    import mujoco as mj

    if not SWATTER_MESH.exists():
        raise FileNotFoundError(f"No swatter mesh at {SWATTER_MESH}")
    spec = scene.mjcf_root
    mesh = spec.add_mesh()
    mesh.name = SWATTER_BODY
    mesh.file = str(SWATTER_MESH)
    body = spec.worldbody.add_body()
    body.name = SWATTER_BODY
    body.mocap = True
    body.pos = tuple(float(x) for x in start_mm)
    geom = body.add_geom()
    geom.name = SWATTER_BODY
    geom.type = mj.mjtGeom.mjGEOM_MESH
    geom.meshname = SWATTER_BODY
    # Centre the paddle head over the mocap point rather than the mesh's own
    # corner origin, so "swatter position" means the thing above the fly.
    geom.pos = (-45.0, -45.0, 0.0)
    geom.rgba = (0.15, 0.15, 0.18, 1.0)
    geom.condim = 3
    geom.density = 200.0


def _add_scene_camera(scene, name: str, tethered: bool) -> None:
    """Add a camera looking at the fly from the side.

    Tethered, the fly does not move, so a world-fixed camera is enough.  Free,
    it drops the height of the frame in about 100 ms, so the camera is parented
    to the thorax and tracks its subtree centre of mass.
    """
    if tethered:
        cam = scene.mjcf_root.worldbody.add_camera()
        cam.pos = (0.0, -12.0, 1.5)
        cam.quat = (0.7071, 0.7071, 0.0, 0.0)  # +y forward, +z up
    else:
        import mujoco as mj

        cam = scene.mjcf_root.body(f"{name}/c_thorax").add_camera()
        # Level with the centre of mass, not above it.  In trackcom the camera
        # keeps a fixed world orientation and only its position follows, so a
        # vertical offset here does not tilt the view back towards the fly -- it
        # just pushes the fly permanently down the frame by that much.
        cam.pos = (0.0, -14.0, 0.0)
        cam.quat = (0.7071, 0.7071, 0.0, 0.0)
        # trackcom keeps the fly centred without inheriting its roll and pitch,
        # which would make a tumbling fly look stationary and the world spin.
        cam.mode = mj.mjtCamLight.mjCAMLIGHT_TRACKCOM
    cam.name = SCENE_CAMERA


def _actuator_id(model, prefix: str) -> int:
    """Resolve an actuator by name, tolerating FlyGym's `-position` suffix."""
    import mujoco as mj

    for candidate in (prefix, f"{prefix}-position", f"{prefix}-motor"):
        i = mj.mj_name2id(model, mj.mjtObj.mjOBJ_ACTUATOR, candidate)
        if i >= 0:
            return i
    raise ValueError(f"No actuator matching {prefix!r} in the compiled model.")
