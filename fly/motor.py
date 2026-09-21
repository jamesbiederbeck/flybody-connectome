"""Motor maps beyond the legs: halteres, abdomen and neck.

`fly.legs` mapped the 381 leg motor neurons. This covers the rest of the VNC
motor pool that has a body part to move, with the same discipline: what the
reconstruction supplies is separated from what was chosen.

The pool is 708 cells. Legs take 381. This module adds:

    hm   16  haltere    -> the two haltere pitch actuators
    ad  214  abdomen    -> seven abdominal joints, yaw and pitch
    nm   24  neck       -> head yaw and pitch

leaving `wm` (67, wings, already driven by `fly.controls`' decode) and `xm`
(6, bare identifiers, no body part identified).

## Why the halteres matter most here

`README.md` records that the halteres are present in the model, that the
connectome has 205 haltere afferents, and that **nothing joins them**: the
haltere actuators were never commanded, the halteres moved 3e-06 rad over 44
wingbeats, and every haltere result in this project is therefore an injected
stimulus rather than a measurement. Driving them from `hm` motor neurons is the
first half of closing that gap -- the second half is deriving afferent drive
from haltere deflection, which needs sensors the model does not have.

Four of the seven `hm` types are named for real haltere muscles: `hDVM MN` is
the dorsoventral power muscle, `hi1`, `hi2` and `hiii2` are steering muscles.
Side comes from `somaSide`, so left cells drive the left haltere.

## What each map is made of

**Grounded**: subclass gives the body region; `somaSide` gives L/R for all of
them; `somaNeuromere` gives the abdominal segment A1-A10, which lines up with
the model's abdomen1-7 chain; and some types carry muscle names.

**Inferred**: that a bilateral *sum* drives a pitch-like degree of freedom and a
left-minus-right *difference* drives a yaw-like one. That is the standard
bilateral-motor assumption and it is not measured here.

**Invented**: nothing is assigned to a joint on a guess. Where a neuromere has
no corresponding joint -- abdominal A8-A10, which are genital segments in a
model whose abdomen stops at 7 -- those cells are dropped rather than folded
into the nearest joint. Head roll is left undriven because no basis exists to
separate it from yaw.
"""
from __future__ import annotations

import numpy as np

# Abdominal neuromere -> the model joint immediately posterior to it. A1 hangs
# the abdomen off the thorax; A2-A7 are the inter-segment joints. A8-A10 have
# no joint in this model and are dropped.
ABDOMEN_JOINT = {
    "A1": "c_thorax-c_abdomen1",
    "A2": "c_abdomen1-c_abdomen2",
    "A3": "c_abdomen2-c_abdomen3",
    "A4": "c_abdomen3-c_abdomen4",
    "A5": "c_abdomen4-c_abdomen5",
    "A6": "c_abdomen5-c_abdomen6",
    "A7": "c_abdomen6-c_abdomen7",
}


def _indices(a, mask, side=None, neuromere=None):
    m = mask.copy()
    if side is not None:
        m &= (a.somaSide == side).to_numpy()
    if neuromere is not None:
        m &= (a.somaNeuromere == neuromere).to_numpy()
    return np.flatnonzero(m).astype(np.int32)


def build(brain, fly):
    """{actuator_name: [(indices, sign), ...]} for halteres, abdomen and neck.

    Names are unprefixed; the caller resolves them against the compiled model.
    """
    from connectome_sim.physiology.common import annotations
    a = annotations(brain.ids)
    t = a.type.fillna("")
    motor = (a.superclass == "vnc_motor").to_numpy()
    out: dict[str, list] = {}
    report: dict[str, dict] = {}

    # --- Halteres -------------------------------------------------------
    # One pitch actuator per side; every hm cell on that side drives it. No
    # attempt to split power from steering muscles, because the model gives
    # the haltere a single degree of freedom to split them across.
    hm = motor & (a.subclass == "hm").to_numpy()
    haltere = {}
    for side, letter in (("L", "l"), ("R", "r")):
        idx = _indices(a, hm, side=side)
        if len(idx):
            out[f"c_thorax-{letter}_haltere-pitch-position"] = [(idx, +1.0)]
            haltere[letter] = int(len(idx))
    report["haltere"] = {"cells": int(hm.sum()), "per_side": haltere,
                         "named_types": ["hDVM MN", "hi1 MN", "hi2 MN", "hiii2 MN"]}

    # --- Abdomen --------------------------------------------------------
    # Segment identity is in the data, so each abdominal neuromere drives the
    # joint behind it: bilateral sum to pitch, left-minus-right to yaw.
    ad = motor & (a.subclass == "ad").to_numpy()
    used, dropped = 0, 0
    for neuromere, joint in ABDOMEN_JOINT.items():
        left = _indices(a, ad, side="L", neuromere=neuromere)
        right = _indices(a, ad, side="R", neuromere=neuromere)
        if not len(left) and not len(right):
            continue
        out[f"{joint}-pitch-position"] = [(left, +1.0), (right, +1.0)]
        out[f"{joint}-yaw-position"] = [(left, +1.0), (right, -1.0)]
        used += len(left) + len(right)
    for neuromere in ("A8", "A9", "A10"):
        dropped += int((ad & (a.somaNeuromere == neuromere).to_numpy()).sum())
    report["abdomen"] = {"cells": int(ad.sum()), "driven": used,
                         "dropped_no_joint": dropped,
                         "segments": sorted(ABDOMEN_JOINT)}

    # --- Neck -----------------------------------------------------------
    # Head pitch from the bilateral sum, head yaw from the difference. Roll is
    # left undriven: with no per-muscle axis assignment it would be the same
    # signal as yaw wearing a different name.
    nm = motor & (a.subclass == "nm").to_numpy()
    left, right = _indices(a, nm, side="L"), _indices(a, nm, side="R")
    if len(left) or len(right):
        out["c_thorax-c_head-pitch-position"] = [(left, +1.0), (right, +1.0)]
        out["c_thorax-c_head-yaw-position"] = [(left, +1.0), (right, -1.0)]
    report["neck"] = {"cells": int(nm.sum()), "left": int(len(left)),
                      "right": int(len(right)), "roll": "undriven, no basis"}

    # --- The jump muscle ---------------------------------------------
    # TTMn and STTMm are classified `wm` in this dataset -- they are thoracic
    # muscles -- but the tergotrochanteral muscle acts on the *trochanter*, and
    # its job is the rapid mesothoracic leg extension that launches a takeoff.
    # So it is mapped to the middle leg's trochanter-femur pitch, in the
    # extending direction, which is the joint the real muscle moves. This is
    # inferred from the muscle's name and known action, not measured here.
    ttm = motor & t.isin(["TTMn", "STTMm"]).to_numpy()
    jump = {}
    for side, letter in (("L", "l"), ("R", "r")):
        idx = _indices(a, ttm, side=side)
        if len(idx):
            out[f"{letter}m_coxa-{letter}m_trochanterfemur-pitch-position"] = [(idx, +1.0)]
            jump[letter] = int(len(idx))
    report["jump"] = {"cells": int(ttm.sum()), "per_side": jump,
                      "target": "middle leg trochanter-femur extension",
                      "basis": "muscle name and action, not measured here"}

    report["not_mapped"] = {
        "wm": int((motor & (a.subclass == "wm").to_numpy()).sum()),
        "wm_note": "wings are driven by fly.controls' decode, not per-muscle",
        "xm": int((motor & (a.subclass == "xm").to_numpy()).sum()),
        "xm_note": "bare identifiers, no body part identified",
    }
    return out, report


class BodyMap:
    """Drives haltere, abdomen and neck actuators from motor-neuron rates."""

    def __init__(self, brain, fly, *, gain=5.0, limit=0.5):
        import mujoco as mj
        self.gain, self.limit = gain, limit
        spec, self.report = build(brain, fly)
        m = fly.model
        self.groups, self.rest = {}, {}
        for name, groups in spec.items():
            aid = mj.mj_name2id(m, mj.mjtObj.mjOBJ_ACTUATOR, f"{fly.name}/{name}")
            if aid < 0:
                continue
            self.groups[name] = (aid, groups)
            j = int(m.actuator_trnid[aid, 0])
            self.rest[name] = float(fly.data.qpos[m.jnt_qposadr[j]])
        self.report["resolved_actuators"] = len(self.groups)
        self.report["unresolved"] = sorted(set(spec) - set(self.groups))

    def act(self, counts, fly, seconds: float) -> dict:
        m, d = fly.model, fly.data
        counts = np.asarray(counts)
        commands = {}
        for name, (aid, groups) in self.groups.items():
            rate = sum(sign * float(counts[idx].sum()) for idx, sign in groups) / seconds
            offset = float(np.clip(self.gain * rate / 1000.0, -self.limit, self.limit))
            lo, hi = m.actuator_ctrlrange[aid]
            target = self.rest[name] + offset
            d.ctrl[aid] = float(np.clip(target, lo, hi)) if hi > lo else target
            commands[name] = offset
        return commands
