"""A closed leg loop: ground contact and joint angles in, leg motor neurons out.

**This mapping is naive and partly arbitrary, and the arbitrary parts are
marked.** Nobody knows which MuJoCo joint a given motor neuron innervates; what
the reconstruction gives us is a muscle *name* per motor neuron, and flybody
gives us a joint name per actuator. Where those names agree about anatomy the
mapping is real. Where they do not, a choice was made and labelled.

What is grounded in the data:

* 381 leg motor neurons carry `somaNeuromere` T1/T2/T3, which is front, middle
  and hind leg, and `somaSide` L/R. So every one of them lands on a specific
  one of the six legs without guesswork.
* 19 of the 38 motor types are named for the muscle they drive -- `Ti flexor
  MN`, `Tr extensor MN`, `Sternal anterior rotator MN` -- and those names say
  which segment moves and in which direction. That is what `MUSCLE_JOINT`
  encodes, flexor negative and extensor positive.
* Leg afferents carry a `class` of `mechanosensory_proprioceptive` or
  `mechanosensory_tactile`, so joint-angle drive and contact drive go to
  different populations rather than one undifferentiated pool.

What is arbitrary, and would be wrong to report as anatomy:

* The remaining 19 motor types are bare identifiers (`MNhl65`, `MNml78`) with
  no muscle in the name. They are left undriven rather than assigned somewhere
  convenient.
* Leg afferents have **no segment label at all** in this reconstruction --
  `somaNeuromere` is null for all 2,604 of them -- so which leg an afferent
  belongs to cannot be recovered. They are split by side where `instance` gives
  one, then divided arbitrarily into thirds across front/middle/hind. A cell's
  assignment to a specific leg is therefore a placeholder, and any result that
  depends on it is measuring the placeholder.
* The gains are hand-set to produce visible motion, not fitted to anything.

So this closes the loop. It does not model leg control.
"""
from __future__ import annotations

import numpy as np

# Muscle name -> (body segment, rotation axis, sign). Sign is +1 for a muscle
# whose name says "extensor"/"promotor"/"levator" and -1 for
# "flexor"/"remotor"/"depressor"/"adductor"; the joint command is the signed sum.
MUSCLE_JOINT = {
    "Sternal anterior rotator MN": ("coxa", "yaw", +1.0),
    "Tergopleural/Pleural promotor MN": ("coxa", "yaw", +1.0),
    "Sternal posterior rotator MN": ("coxa", "yaw", -1.0),
    "Pleural remotor/abductor MN": ("coxa", "yaw", -1.0),
    "Tergotr. MN": ("coxa", "roll", +1.0),
    "Sternal adductor MN": ("coxa", "roll", -1.0),
    "Sternotrochanter MN": ("coxa", "pitch", +1.0),
    "Tr extensor MN": ("trochanterfemur", "pitch", +1.0),
    "Tr flexor MN": ("trochanterfemur", "pitch", -1.0),
    "Acc. tr flexor MN": ("trochanterfemur", "pitch", -1.0),
    "Fe reductor MN": ("trochanterfemur", "roll", +1.0),
    "Ti extensor MN": ("tibia", "pitch", +1.0),
    "Ti flexor MN": ("tibia", "pitch", -1.0),
    "Acc. ti flexor MN": ("tibia", "pitch", -1.0),
    "Ta levator MN": ("tarsus1", "pitch", +1.0),
    "Ta depressor MN": ("tarsus1", "pitch", -1.0),
    "ltm MN": ("tarsus1", "pitch", -1.0),
    "ltm1-tibia MN": ("tarsus1", "pitch", -1.0),
    "ltm2-femur MN": ("tarsus1", "pitch", -1.0),
}

NEUROMERE_SEGMENT = {"T1": "f", "T2": "m", "T3": "h"}
LEGS = ("lf", "lm", "lh", "rf", "rm", "rh")


def actuator_name(leg: str, segment: str, axis: str) -> str:
    """flybody's actuator naming, which differs by where the joint sits."""
    if segment == "coxa":
        return f"c_thorax-{leg}_coxa-{axis}-position"
    if segment == "trochanterfemur":
        return f"{leg}_coxa-{leg}_trochanterfemur-{axis}-position"
    if segment == "tibia":
        return f"{leg}_trochanterfemur-{leg}_tibia-pitch-position"
    if segment == "tarsus1":
        return f"{leg}_tibia-{leg}_tarsus1-pitch-position"
    raise ValueError(f"Unmapped segment: {segment!r}")


def motor_map(brain):
    """{leg: {(segment, axis): [(indices, sign), ...]}} from muscle names.

    Grounded: neuromere gives the leg, side gives L/R, the type name gives the
    muscle. Unnamed MN types are dropped, not reassigned.
    """
    from connectome_sim.physiology.common import annotations
    a = annotations(brain.ids)
    motor = ((a.superclass == "vnc_motor")
             & a.subclass.isin(["fl", "ml", "hl"])).to_numpy()
    out, dropped = {leg: {} for leg in LEGS}, {}
    for t, (segment, axis, sign) in MUSCLE_JOINT.items():
        hit = motor & (a.type == t).to_numpy()
        for neuromere, seg_letter in NEUROMERE_SEGMENT.items():
            for side, side_letter in (("L", "l"), ("R", "r")):
                idx = np.flatnonzero(hit
                                     & (a.somaNeuromere == neuromere).to_numpy()
                                     & (a.somaSide == side).to_numpy())
                if len(idx):
                    leg = f"{side_letter}{seg_letter}"
                    out[leg].setdefault((segment, axis), []).append(
                        (idx.astype(np.int32), sign))
    named = set(MUSCLE_JOINT)
    for t in sorted(set(a.type[motor].dropna()) - named):
        dropped[t] = int((motor & (a.type == t).to_numpy()).sum())
    return out, dropped


def sensory_map(brain, seed: int = 20260919):
    """{leg: {'proprioceptive': idx, 'tactile': idx}}.

    Side comes from `instance`'s _L/_R suffix where present. **Segment does
    not exist in the data**, so the per-side pool is shuffled once with a fixed
    seed and cut into equal thirds. That third is a placeholder for "which
    leg", not a claim about one.
    """
    from connectome_sim.physiology.common import annotations
    a = annotations(brain.ids)
    leg_ish = a.subclass.isin(["leg", "leg bristle", "campaniform sensilla",
                               "hair plate", "chordotonal organ"]).to_numpy()
    sensory = a.superclass.isin(["vnc_sensory", "sensory_ascending"]).to_numpy()
    base = leg_ish & sensory
    instance = a.instance.fillna("")
    rng = np.random.default_rng(seed)
    out = {leg: {} for leg in LEGS}
    for cls, key in (("mechanosensory_proprioceptive", "proprioceptive"),
                     ("mechanosensory_tactile", "tactile")):
        pool = base & (a["class"] == cls).to_numpy()
        sided = {
            "l": np.flatnonzero(pool & instance.str.endswith("_L").to_numpy()),
            "r": np.flatnonzero(pool & instance.str.endswith("_R").to_numpy()),
        }
        # Most leg afferents have no instance at all -- 865 of 1,154
        # proprioceptive and 208 of 213 tactile -- so sided labels alone would
        # discard almost the whole population. The unsided remainder is dealt
        # evenly between the two sides instead of dropped, which is another
        # placeholder and is why side is not a measured variable here either.
        unsided = rng.permutation(np.flatnonzero(pool & (instance == "").to_numpy()))
        half = len(unsided) // 2
        sided["l"] = np.concatenate([sided["l"], unsided[:half]])
        sided["r"] = np.concatenate([sided["r"], unsided[half:]])
        for side_letter, members in sided.items():
            members = rng.permutation(members)
            for k, seg_letter in enumerate("fmh"):
                out[f"{side_letter}{seg_letter}"][key] = members[k::3].astype(np.int32)
    return out


class LegLoop:
    """Ground contact and joint deviation in, leg joint commands out."""

    def __init__(self, brain, fly, *, proprioceptive_gain=6.0, tactile_gain=8.0,
                 motor_gain=0.02, command_limit=0.5, seed=20260919):
        import mujoco as mj
        self.motor, self.unmapped = motor_map(brain)
        self.sensory = sensory_map(brain, seed)
        self.proprioceptive_gain = proprioceptive_gain
        self.tactile_gain = tactile_gain
        self.motor_gain = motor_gain
        self.command_limit = command_limit
        m = fly.model
        self.actuators, self.joints = {}, {}
        for leg, joints in self.motor.items():
            for (segment, axis) in joints:
                name = f"{fly.name}/{actuator_name(leg, segment, axis)}"
                aid = mj.mj_name2id(m, mj.mjtObj.mjOBJ_ACTUATOR, name)
                if aid < 0:
                    continue
                self.actuators[(leg, segment, axis)] = aid
                self.joints[(leg, segment, axis)] = int(m.actuator_trnid[aid, 0])
        self.contact_sensor = {}
        for leg in LEGS:
            # Sensors are registered unprefixed while actuators carry the fly
            # name, so try both rather than assuming one scheme.
            for name in (f"ground_contact_{leg}_leg", f"{fly.name}/ground_contact_{leg}_leg"):
                sid = mj.mj_name2id(m, mj.mjtObj.mjOBJ_SENSOR, name)
                if sid >= 0:
                    self.contact_sensor[leg] = (int(m.sensor_adr[sid]), int(m.sensor_dim[sid]))
                    break
        # Rest pose is whatever the fly settled into; commands are deviations
        # from it so the legs do not snap to zero on the first tick.
        self.rest = {k: float(fly.data.qpos[m.jnt_qposadr[j]]) for k, j in self.joints.items()}

    def sense(self, fly):
        """Stimulation list: joint deviation drives proprioceptors, ground
        contact drives tactile afferents, per leg."""
        m, d = fly.model, fly.data
        stim = []
        for leg in LEGS:
            deviation, n = 0.0, 0
            for (lg, segment, axis), j in self.joints.items():
                if lg != leg:
                    continue
                deviation += abs(float(d.qpos[m.jnt_qposadr[j]]) - self.rest[(lg, segment, axis)])
                n += 1
            if n:
                idx = self.sensory[leg].get("proprioceptive")
                if idx is not None and len(idx):
                    stim.append((idx, float(self.proprioceptive_gain * deviation / n)))
            if leg in self.contact_sensor:
                adr, dim = self.contact_sensor[leg]
                force = float(np.linalg.norm(d.sensordata[adr:adr + dim]))
                idx = self.sensory[leg].get("tactile")
                if idx is not None and len(idx) and force > 0:
                    stim.append((idx, float(self.tactile_gain * np.tanh(force))))
        return [(i, c) for i, c in stim if c > 0] or None

    def act(self, counts, fly, seconds: float):
        """Signed sum of motor-neuron rates per joint, as a position offset."""
        m, d = fly.model, fly.data
        counts = np.asarray(counts)
        commands = {}
        for leg, joints in self.motor.items():
            for key, groups in joints.items():
                aid = self.actuators.get((leg, *key))
                if aid is None:
                    continue
                rate = sum(sign * float(counts[idx].sum()) for idx, sign in groups) / seconds
                offset = float(np.clip(self.motor_gain * rate / 1000.0,
                                       -self.command_limit, self.command_limit))
                target = self.rest[(leg, *key)] + offset
                lo, hi = m.actuator_ctrlrange[aid]
                d.ctrl[aid] = float(np.clip(target, lo, hi)) if hi > lo else target
                commands[(leg, *key)] = offset
        return commands

    def summary(self) -> dict:
        return {
            "legs": {leg: {f"{s}-{a}": int(sum(len(i) for i, _ in g))
                           for (s, a), g in joints.items()}
                     for leg, joints in self.motor.items()},
            "driven_actuators": len(self.actuators),
            "contact_sensors": len(self.contact_sensor),
            "sensory_cells": {leg: {k: int(len(v)) for k, v in d.items()}
                              for leg, d in self.sensory.items()},
            "unmapped_motor_types": self.unmapped,
            "caveat": ("Motor side/leg and muscle identity come from the reconstruction; "
                       "which MuJoCo joint a muscle drives is inferred from its name. "
                       "Afferents have no segment label, so their assignment to a "
                       "specific leg is an arbitrary fixed-seed split."),
        }
