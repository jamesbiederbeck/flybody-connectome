# Experiment log

Newest first. Each entry: what was asked, what was run, what came back, and what
it changed. Negative results and corrections to earlier entries stay in — an
entry is never edited to look better in hindsight, it gets a follow-up.

Conventions used throughout: a fresh `NativeBrain` (or a verified state reset)
per condition, because both brain and physics state carry; every claim labelled
measured or inferred; and a stated control for anything that could be produced
by the setup rather than the thing being measured.

---

## 2026-09-20 — Leg-drive gain threshold: the walking latch is a step function, not a ramp (`experiments/leg_gain_threshold.py`)

**Asked:** turn down `fly/legs.py`'s leg-sensory drive gains and see whether the
walking loop settles into a less-saturated intermediate state instead of the
full `cb_intrinsic` ~32 Hz/cell attractor already measured in
`walk-characterization.json`.

**Result: no intermediate state exists.** Swept `proprioceptive_gain`/
`tactile_gain` together as a fraction of default (6.0/8.0), fresh brain and
body per condition, 200 ticks/60 settle/motor_gain 5.0 throughout:

| fraction | gains | cb_intrinsic Hz | displacement |
| --- | --- | ---: | ---: |
| 1.0x (default) | 6.0 / 8.0 | 32.06 | 3.64 mm |
| 0.9x | 5.4 / 7.2 | 29.27 | 2.65 mm |
| 0.8x | 4.8 / 6.4 | 0.00 | 0.04 mm (floor) |
| 0.7x – 0.01x | — | 0.00 | 0.04 mm (floor) |

Everything from 0.8x down is indistinguishable from the network's own resting
floor -- the fly does not walk at all. The transition sits in a narrow band
between 0.8x and 0.9x of default gain, and even at 0.9x the network is already
most of the way to full saturation (29.27 of 32.06 Hz), not partway. This is
the same two-states behaviour as
[`findings/02-two-states.md`](../../connectome-lab/findings/02-two-states.md),
now confirmed along the leg-loop's own drive-gain axis rather than isolated
pulse amplitude.

---

## 2026-09-20 — SApp latch, fine-grained: the "saturated attractor" is the mushroom-body/antennal-lobe circuit, not a uniform seizure (`experiments/sapp_latch_census.py`)

**Asked:** the existing SApp/CRZ latch characterization only went to
`superclass`/`subclass` resolution (27/49 values). Re-run the identical
SApp\_pair\_30mV protocol (drive 30 mV/500 ms on SApp\_R body\_id 101048 +
SApp\_L body\_id 136883, 500 ms dark settle, 1000 ms post-drive-removed
window) and report at `class`, `entryNerve`, `exitNerve` and `somaNeuromere`
resolution -- all measured annotation columns, not inferred groupings.

**Result: the latch is not uniform.** By `class`:

| class | cells | latched Hz |
| --- | ---: | ---: |
| MBON | 97 | 228.0 |
| ALLN | 420 | 180.4 |
| DAN | 340 | 153.0 |
| ALPN | 686 | 128.1 |
| Kenyon_Cell | 4,064 | 122.6 |
| CX | 2,950 | 12.7 |
| olfactory | 2,639 | 7.8 |
| visual | 6,091 | **0.0** |
| mechanosensory (all 3 classes) | 5,756 | **0.0** |

The entire mushroom-body/antennal-lobe circuit (MBON, DAN, ALPN, ALLN, Kenyon
cells -- the same KC-to-MBON11 wiring `findings/05-plasticity-cannot-reach-
the-controller.md` already identified as the engine's only plasticity locus)
fires at 4-7x the superclass-level ~32 Hz average, while vision and every
mechanosensory class stay at exactly zero throughout. `somaNeuromere` agrees:
deutocerebrum (DC, where the antennal lobes sit) is hottest at 132.9 Hz, over
5x the next segment, while the thoracic segments (T1-T3, where leg motor
circuitry lives) are the *lowest* of any driven segment at 2.8-3.5 Hz.
`entryNerve` shows only the antennal nerve (AN) and pharyngeal nerve (aPhN)
carrying meaningful drive; every leg and abdominal nerve trunk sits at zero.

Baseline is 0.000 Hz everywhere in this table -- not because the latch
suppresses those classes, but because the network's own dark resting state is
already close to silent (see the extended zero-stimulation baseline run
referenced in this session). So this is a rise from a silent floor into the
AL/MB circuit specifically, not a shift between two nonzero levels, and not a
generic whole-brain runaway. A haltere afferent (SApp) has no obvious
anatomical reason to have privileged access to the mushroom body over vision
-- promoted to `findings/09-the-latch-is-the-mushroom-body.md`.

---

## 2026-09-20 — Scent taxis: delivery-verified null, and the displacement metric's own run-to-run noise turns out bigger than any effect it could show (`experiments/scent_taxis.py`)

**Asked:** does a fixed static scent source bias the leg loop's net walking
direction? Layer one more channel onto `fly/legs.py`'s existing stimulation
list -- olfactory current into ORN_DA1, split left/right by bearing to the
source -- and measure net displacement projected onto the fly-to-source
direction, plus `cb_intrinsic` as the saturation check.

**Invented choices, stated up front.** Glomerulus **ORN_DA1**: one of ~50
glomerulus types with a mapped ORN population (204 cells; `rootSide` splits
105 R / 51 L / 48 `unknown`, matching the `instance` suffix exactly) --
picked arbitrarily among the available glomeruli, not a claim about what this
population smells biologically. The 48 unknown-laterality cells are excluded
from injection; only the 156 sided cells are driven, and that R/L imbalance
(105 vs 51) is an inherited bias in exactly the sense `AGENTS.md` already
flags for the eyes (1,107 left / 2,228 right) -- an asymmetric response here
cannot be attributed to the scent's side without ruling that out, and this
run does not rule it out. Falloff: `exp(-distance / 10mm)`, invented for
having the right qualitative shape, no measurement behind the length scale.
Gain 8 mV, same order as `fly.legs`'s own tactile gain, also invented. L/R
split by the cosine of bearing against the fly's right-axis (dead ahead =
50/50, abeam one side = ~100/0) -- an engineered proxy for "which side smells
it more," not a measured convergence rule. Heading read via
`mujoco.mju_rotVecQuat` on the thorax quaternion, local +y forward / +x
right, per `fly.body`'s own scene-camera comment ("+y forward, +z up"); no
new orientation math. Source placed 15 mm from spawn (about 2x the ~6.7 mm
leg-loop-plus-body displacement this session's own characterization measured
at the same motor gain). **No scent-CRZ association was attempted or
simulated** -- this project's only plasticity is the fixed 4,184-edge
KC->MBON11 pathway, CRZ is confirmed separately to not be part of it, and
there is no learning mechanism here that could produce a real one.

**Four conditions, each a fresh `NativeBrain` + fresh `fly.body.build()`**
(this project's own convention -- reused state has produced wrong answers
before): scent ahead, behind, to one side (right, arbitrary), and no-scent,
200 ticks, 60 settle, motor-gain 5, brain-hz 30 -- matching this session's own
leg-loop characterization for comparability.

| condition | displacement vec (mm) | toward-source (mm) | cb_intrinsic Hz/cell | total spikes |
| --- | --- | ---: | ---: | ---: |
| ahead | (4.379, -0.449, -0.067) | -0.449 | 31.898 | 10,581,831 |
| behind | (2.915, 1.925, -0.156) | -1.925 | 31.887 | 10,572,789 |
| side | (1.735, 3.639, -0.108) | 1.735 | 31.921 | 10,594,613 |
| none | (5.102, -2.230, -0.252) | -- | 31.895 | 10,582,201 |

Differencing against `none` projected onto each condition's own bearing
(`d_none . bearing`: ahead -2.230, behind 2.230, side 5.102) gives deltas of
**+1.781 (ahead), -4.155 (behind), -3.367 (side)** -- no consistent sign, no
shape that reads as "toward" or "away." Spike totals across all four spread
only 0.2% (10.573M-10.595M) and `cb_intrinsic` spreads 0.1%, while the
trajectories' headings spread roughly 88 degrees. That heading spread is
addressed below -- it turns out not to require an injection at all.

**The reproducibility check that changes what this table can claim.** Reran
the no-scent condition with parameters identical in everything that reaches
the `none` arm (gain and distance are unused when there is no source; only
`--conditions`/`--out` differed, as part of the gain-54 arm below):
displacement **3.012 mm**, vector (2.999, -0.219, -0.180) -- against the
first run's 5.573 mm, (5.102, -2.230, -0.252). Same code, same seed, nothing
injected. Displacement magnitudes differ by 2.56 mm; the two endpoints
themselves are 2.91 mm apart in space, (2.103, -2.011, -0.072); and heading
differs by roughly 19 degrees between them. Total spike counts between the
two `none` runs differed by only 1,770 out of 10.58M (0.017%), so a tiny
per-tick difference is being chaotically amplified into a large displacement
difference over 200 ticks. **This means the ~88 degree heading spread and the
"very different place" reading of the main table are not attributable to the
olfactory injection at all** -- the same spread appears between two runs of
the identical no-op condition. Cause is **inferred, not measured**: the only
non-deterministic input in this loop is the per-tick `mapping(fly.ommatidia())`
camera render, which `connectome-lab/REPRODUCIBILITY.md` (rule 4) already
documents as not run-to-run identical because the eye cameras sit inside the
control loop -- this was not isolated or confirmed here, only the divergence
itself was measured.

**Recomputing the deltas against this second `none` sample makes the point
directly, with no new runs needed:**

| bearing | delta vs `none` #1 (5.102, -2.230) | delta vs `none` #2 (2.999, -0.219) |
| --- | ---: | ---: |
| ahead | +1.781 | -0.230 |
| behind | -4.155 | -2.145 |
| side | -3.367 | -1.264 |

Every delta shifts by roughly 2 mm between the two choices of baseline, and
`ahead` **flips sign**. The differenced metric is not measuring the scent; it
is measuring which of two equally-valid no-scent samples happened to be
picked as the reference. **None of the ahead/behind/side deltas can be
attributed to scent direction on this evidence.**

**A delivery-verified null, not an underpowered one.** Raising gain to 54 mV
(peak injected 12.05 mV at 15 mm, vs. 1.78 mV in the main run) drove ORN_DA1
to **46.6 Hz/cell (R) / 40.2 Hz/cell (L)**, against 1.32/1.78 Hz/cell with no
injection at all -- roughly 30x. `cb_intrinsic` moved 31.894 -> 33.062. So the
stimulus demonstrably reaches and drives the target population hard. The
`side` displacement at this gain was 4.137 mm, (1.406, 3.884, -0.224) -- not
distinguishable in kind from the 8 mV run's 4.033 mm, and still inside the
noise band the reproducibility check established. This rules out "the signal
was too weak to matter" as the explanation for the null.

**A symmetric-split control** (same total intensity and time-course, forced
50/50 L/R, run at the original 8 mV `side` condition) gave 2.809 mm, (2.799,
0.198, -0.135), toward-source 2.799 mm -- a similar order of magnitude to the
directional `side` arm's 1.735 mm. It was meant to separate a direction-
specific effect from generic perturbation (`experiments/jo_specificity_control.py`
asks the same question about JO), but with the no-injection control itself
varying by 2.56 mm between two identical runs, this comparison is subsumed by
the reproducibility finding above and cannot do that discriminating work here.

**Design limitation, stated rather than glossed over:** `ahead` and `behind`
both start at lateral ~0 (50/50 L/R) at tick 0 -- the injection scheme
carries no front/back information, only left/right. Over the run they diverge
only in total delivered intensity as distance closes or opens, not in a
fore/aft signal, so that pair is not a tested fore/aft contrast.

**Baseline was already saturated.** `cb_intrinsic` sits at ~31.9 Hz/cell with
the leg loop alone and no scent at all, matching the ~32-33 Hz/cell signature
`findings/02-two-states.md` and this session's own SApp/leg-loop entries use
for the generic saturated attractor. So there was no sub-saturation dynamic
range for a graded scent signal to act within even before the reproducibility
problem is considered -- consistent with the standing prior that a
weak-to-strong odor gradient either does nothing or pushes into the same
generic regime regardless of direction. It also fits this session's separate
finding that this network does not drift into that state at rest (12.5 s flat
baseline, `cb_intrinsic` at exactly 0) -- here the leg loop alone is already
enough to hold it saturated, before any scent is added.

**Conclusion.** No directional bias found, and the null is not attributable
to insufficient stimulus strength (delivery-verified at ~30x baseline ORN
firing). But the sharper finding is methodological: net thorax displacement
over 200 ticks, driven through this leg loop, is not reproducible run-to-run
by more than the effect sizes this experiment was built to detect, for
reasons not isolated here (inferred: the per-tick retinal render). That
ceiling applies to any future experiment using displacement-toward-a-target
as a metric on this leg loop, not just this one -- worth fixing (isolate and
either eliminate or characterize the render noise, or take enough repeats per
condition to average it out) before trusting a displacement-vector result
from this harness again.

Status: measured; null, with the run-to-run noise floor identified but not
characterized or fixed -- that characterization is the natural follow-up and
was not done in this session. Output: `outputs/scent_taxis/run.json`,
`run_suprathreshold.json`, `run_symmetric_control.json`.

---

## 2026-09-20 — SApp pulsatile drive: a threshold in pulse count, not a frequency tuning curve (`haltere_sapp_pulse.py`, experiment 1)

**Asked:** drive SApp's two responsive cells (101048 R, 136883 L — see the
2026-09-19 single-cell-sweep entry) with discrete spike-timed pulses instead of
DC, in phase, and sweep frequency.

**Setup.** Pulse width 1 ms — invented, chosen short relative to the 20 ms
membrane tau and 1.8 ms synaptic delay so a pulse approximates one input spike
rather than a sustained step. Amplitude calibrated per cell (smallest single
1 ms pulse that reliably fires it once from a fresh reset): both cells needed
150 mV, well above the 20 mV that fires them over a 500 ms sustained window —
an isolated 1 ms pulse has to cross threshold on its own, with no time to
integrate. Shared 150 mV used for both cells throughout. Frequencies 5, 10, 30,
60, 120, 218, 300, 400 Hz, both cells pulsed in phase, 1000 ms window, 1 ms
bins, fresh reset per frequency. Readouts: b1/b2/hg1/power (`haltere_axis_pairs`
groups) plus an added DLM-only split and a global spike count.

**Zero response below 120 Hz, then falling response per pulse above it.**

| f (Hz) | pulses | response/window | response/pulse |
| ---: | ---: | ---: | ---: |
| 5–60 | 5–60 | 0 | 0 |
| 120 | 120 | 2320 | 19.3 |
| 218 | 218 | 2674 | 12.3 |
| 300 | 300 | 2574 | 8.6 |
| 400 | 400 | 2547 | 6.4 |

(response/window = summed non-baseline spikes across b1/b2/hg1/power readouts,
DLM excluded from the sum since `power` already contains both DLM types and
summing both double-counts it — DLM is still reported per-trial in full.
Baseline is exactly 0 for every readout group under dark/no-sugar input,
confirmed both as a single 1000 ms call and as 2000×0.5 ms calls with no
stimulation, so non-baseline subtraction is a no-op here, not a correction.)

**This is not evidence of frequency tuning, and it is not evidence of a clean
pulse-count integrator either — it's a threshold in total pulses plus falling
per-pulse efficacy above it, and the two are confounded in this sweep.** Below
120 Hz nothing gets through at all (0 of 120 pulses' worth of drive reaches the
readouts); above it, response per pulse falls monotonically (19.3 → 12.3 → 8.6
→ 6.4) as frequency rises. Because frequency and pulse count move together
across this sweep (a fixed 1000 ms window means higher Hz is also more
pulses), this cannot distinguish "the floor is at ~120 pulses" from "the floor
is at ~120 Hz" — that is an open question, not resolved here. Selection rule
for experiment 2: largest summed non-baseline response (218 Hz), plus any
frequency within 20% of it (300 and 400 Hz both qualified; kept the top two,
218 and 300 Hz — invented margin, stated here). Reset verified: repeating the
first frequency (5 Hz) after the full sweep reproduced exactly.

**A numerical caveat found and avoided, not the pathway's own property.**
Reducing the per-call step duration below `bin_ms=0.25` (down to 0.1 ms,
tried while chasing phase resolution for experiment 2 below) silently zeroes
every wing-motor readout group while the network's own global spike count
stays large — the directly-stimulated cells and general network activity keep
firing, but nothing registers in b1/b2/hg1/power/DLM. This reproduces at both
200 ms and 1000 ms windows, so it is not a duration effect; it is a
sensitivity of this engine to very short per-`Brain.step` durations, not
tested further here. `bin_ms=0.5` (already used in `haltere_depth_phase.py`)
does not show it and is used throughout.

Status: measured, complete. Output: `outputs/haltere_sapp_pulse.json`
(`experiment1`).

---

## 2026-09-20 — SApp pulsatile drive: phase between the two cells changes the response, but not in a shape this design can characterize (`haltere_sapp_pulse.py`, experiment 2)

**Asked:** at the frequency(ies) experiment 1 favoured, sweep the phase offset
of R (101048) relative to L (136883) from -180 to +180 degrees.

**Setup.** 218 and 300 Hz (experiment 1's selection), 13 phase steps at 30
degree spacing (-180 to +180 inclusive), same 150 mV/1 ms pulses. Verified,
not assumed: total pulse count per cell is exactly constant across all 13
phases at both frequencies (218 and 300 respectively) — computed directly from
the pulse-bin schedule, so the spread below is not an artifact of some phase
conditions delivering more pulses than others.

**Bin size mattered more than expected, and the fix is recorded so it isn't
rediscovered.** 30-degree steps are a 0.38 ms (218 Hz) / 0.28 ms (300 Hz) time
shift — smaller than experiment 1's 1 ms bins, so most of the 13 phases would
have snapped onto the same discretized pulse pattern there. Dropping bin size
to resolve this hit the `bin_ms<=0.25` engine artifact noted in experiment 1's
entry; settled on `bin_ms=0.5`, window shortened to nothing (kept at 1000 ms,
same as experiment 1) — 12 of 13 phase conditions are distinguishable at both
frequencies (the theoretical ceiling: -180 and +180 degrees are the same
condition by construction).

**The response does vary with phase, and at a different scale per frequency:**

| frequency | min | max | spread |
| ---: | ---: | ---: | ---: |
| 218 Hz | 2827 | 3532 | 25% |
| 300 Hz | 2805 | 3148 | 12% |

This is on a bit-reproducible native simulation (the same reset-verification
convention as experiment 1's; repeating a trial exactly reproduces it), and
pulse count is held exactly constant across phase, so the spread is real and
attributable to relative timing, not to noise or to a pulse-count confound —
both checked, not assumed. **What it does not establish is a phase code.**
Response varies with phase; whether that variation is a smooth, systematic
function of phase (a real tuning curve) or an irregular sensitivity to which
bins the pulses happen to land in was not tested — no shape (sinusoidal,
peaked, monotone) was fit, and none should be inferred from 12 points with no
repeat-trial baseline. The two frequencies also differ in how much they vary
(25% vs 12%), which is itself worth carrying forward rather than averaging
into one number.

**Answer to the motivating question (LOG's 2026-09-19 leave-one-out entry:
"can SApp's own L/R balance support a differential control line?"):** the two
cells' drive sums — the pathway responds to pulses on either/both cells, per
experiment 1 — but nothing here shows it *compares* them. A control line built
on relative timing between SApp-L and SApp-R would need a demonstrated,
repeatable phase-response shape, which this design did not establish either
way.

Status: measured, complete, with an open question flagged (phase-response
shape untested). Output: `outputs/haltere_sapp_pulse.json` (`experiment2`).

---

## 2026-09-20 — SApp continuous drive: no sub-threshold summation, and "direction matters" turns out to mean "which cell crosses its own threshold" (`haltere_sapp_threshold.py`, experiment 3)

**Asked:** on SApp's two responsive cells, at DC/tonic current: (3a) each
cell's own threshold, swept 20 mV down to 0 in 1 mV steps; (3b) whether driving
both together lowers the threshold below either alone; (3c) whether the
*direction* of the (V_L, V_R) drive vector matters, holding its magnitude
fixed.

**3a — clean, monotone individual thresholds, and they differ.** 500 ms
sustained drive (`SUSTAIN_MS`, matches `haltere_axis_pairs.py`'s convention),
DLM spike count as the crossing readout. R (101048): 0 DLM spikes at 14 mV,
328 at 15 mV — threshold 15 mV. L (136883): 0 at 17 mV, 337 at 18 mV —
threshold 18 mV. Both monotone (no zero above their threshold once crossed) at
this resolution — this pathway is documented non-monotone in current
elsewhere in this repo (leave-one-out entry, 1061→653→597), so monotonicity
here was checked, not assumed, and it held. Reset verified: repeating each
sweep's first voltage reproduced exactly.

**3b — the joint threshold equals R's own threshold, not below it.** Both
cells driven equally, stepped down from 19 mV (`max(15,18)+1`) in 0.5 mV
steps: nonzero DLM at 15.0 mV (323 spikes), zero at 14.5 mV. **No sub-threshold
summation** — R's own 15 mV threshold is the whole story; L's simultaneous
15 mV (2 below its own 18 mV solo threshold) contributes nothing measurable to
crossing it earlier. This directly answers the caveat flagged in the
2026-09-19 single-cell-sweep entry ("silent alone is not the same as
contributing nothing in combination") for this specific pair: **it is** the
same. Full range swept to 0 mV with no early stopping, because early-stopping
on the first zero would have assumed monotonicity this repo's own findings say
not to assume.

**3c — direction matters, and it has a mechanistic explanation: whichever
component crosses its own individual threshold.** Magnitude fixed at
`M = sqrt(2) * 15.0 = 21.21 mV` (3b's joint threshold's Euclidean norm, since
3b drives both cells equally); angle swept 0-90 degrees, `V_L = M*cos(theta)`,
`V_R = M*sin(theta)`. This is one operational reading of an ambiguous
instruction, stated here so the result is interpretable independent of that
choice: a genuine 2D vector sweep at constant Euclidean norm, not a fixed-sum
allocation.

| theta | V_L | V_R | DLM | L alone supra (>=18)? | R alone supra (>=15)? |
| ---: | ---: | ---: | ---: | :---: | :---: |
| 0.00 | 21.21 | 0.00 | 391 | yes | — |
| 11.25 | 20.81 | 4.14 | 390 | yes | no |
| 22.50 | 19.60 | 8.12 | 372 | yes | no |
| **33.75** | **17.64** | **11.79** | **0** | **no** | **no** |
| 45.00 | 15.00 | 15.00 | 323 | no | yes (at) |
| 56.25 | 11.79 | 17.64 | 397 | no | yes |
| 67.50 | 8.12 | 19.60 | 393 | no | yes |
| 78.75 | 4.14 | 20.81 | 350 | no | yes |
| 90.00 | 0.00 | 21.21 | 550 | — | yes |

Every one of the 9 points is explained by that two-column rule with no
residual: response is zero exactly once, at theta=33.75 degrees, which is
exactly the one point where *neither* component's own share reaches that
cell's own 3a threshold (V_L=17.64 < 18, V_R=11.79 < 15) — and 3b already
established there is no cross-cell summation to bridge that gap. Every other
point has at least one component individually supra-threshold and gives a
nonzero response of the same rough scale as that cell's own 3a sweep at a
similar voltage. **So "direction matters" is true, but not because of any
joint directional tuning** — it is fully accounted for by two independent
per-cell thresholds and the absence of summation between them (3b). theta=45
degrees (V_L=V_R=15.0) reproduces 3b's V_each=15.0 mV row exactly (DLM 323,
global 464346 both times) — the two code paths for equal joint drive agree to
the digit, which is the sanity check this design was built to allow, not an
independent finding.

Status: measured, complete. One bug found and fixed before this ran clean:
`_find_threshold` looked up the wrong dict key for the joint/direction rows
(`voltage_mV` vs `voltage_each_mV`), caught by the crash it caused rather than
silently returning a wrong threshold. Output:
`outputs/haltere_sapp_threshold.json`.

---

## 2026-09-20 — Firing the giant fibre embodied: a postural twitch, not a jump

**Asked:** fire DNp01 in the body and see whether the fly leaves the ground.

**Setup.** `fly/jump.py`. TTMn and STTMm are classified `wm` in this dataset,
but the tergotrochanteral muscle acts on the trochanter and its job is the
mesothoracic leg extension that launches a takeoff, so `fly/motor.py` maps it to
the middle leg's trochanter-femur extension. That mapping is inferred from the
muscle's name and known action, not measured here. Leg and body motor maps
active throughout; injection into the 2 DNp01 cells from tick 30 of 120.

**First run was confounded, again, in the way the swatter run was.** With the
leg loop's sensory injection active, `dnp01_per_tick` was **0.0 at every
current including 40**. That injection holds the network at ~59k spikes/tick
against a ~21k resting rate, and in that saturated regime DNp01 is suppressed
and cannot be fired at all -- which E-GF had already measured as the giant
fibre's own rate collapsing under high drive. The leg sensory injection is now
off by default in this runner, with the motor path still connected so the body
can move.

**Result, network at rest:**

| DNp01 current | DNp01/tick | TTM/tick | rise | peak upward velocity | min contacts | airborne ticks |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0.00 | 0.00 | 0.0015 mm | 0.0003 | 7 | 0 |
| 20 | **4.90** | 0.683 | 0.024 mm | 0.201 | 5 | 0 |
| 40 | 0.342 | 1.583 | **0.124 mm** | **2.221** | **1** | 0 |
| 60 | 0.00 | 2.392 | 0.154 mm | 1.537 | 2 | 0 |

1. **Something real happens.** The uninjected control is motionless -- 0.0015 mm
   of drift, all seven contacts held. At current 40 the body rises 0.124 mm with
   a peak upward velocity of 2.22 mm/s and contacts drop from 7 to 1, which is
   five legs coming off the ground.

2. **It is not a jump.** `airborne_ticks` is **0** in every arm. The fly never
   leaves the ground. A 0.15 mm rise on a body sitting 1.24 mm up is a postural
   twitch.

3. **The giant fibre suppresses itself as drive rises.** DNp01 goes 4.90 →
   0.342 → 0.00 across currents 20, 40, 60 while TTM output keeps climbing
   0.683 → 1.583 → 2.392. The downstream effect grows while the driven cell
   falls silent, which is the same signature E-SIGN found in the haltere
   pathway and E-GF found on spikes alone.

**Conclusion.** The escape pathway produces a measurable, controlled postural
response from the giant fibre down, and does not produce a takeoff. Whether that
is because TTM is mapped to a single joint, because the gains are hand-set,
or because a real jump needs coordinated multi-joint extension with wing
deployment, is untested. The honest statement is that firing DNp01 lifts five
of six legs and moves the body a tenth of a millimetre.

**Repeated mistake worth naming.** This is the second time a saturating current
injection has silently invalidated a measurement in this repo -- first the
swatter, now the giant fibre. Any experiment that measures a specific
population's firing needs the rest of the injection off, or it is measuring the
attractor.

---

## 2026-09-20 — Light adaptation added to the photoreceptors; it helps 4-8x and is not enough

**Asked:** are we stimulating the visual system wrong? Then: fix it, opt-out.

**The defect.** Luminance reached the network through `30*L/(0.02+L)`, a
Naka-Rushton curve with a fixed semisaturation of 0.02. Measured against the lit
MuJoCo scene, median receptor luminance is **0.53** -- 27x past semisaturation,
on the flat top of the curve.

| luminance | sensitivity (mV per unit L) |
| --- | ---: |
| 0.02 (semisaturation) | 375.00 |
| 0.30 | 5.86 |
| **0.53 (scene median)** | **1.96** |
| 1.00 | 0.58 |

**192x less sensitive at the operating point the scene occupies.** The swatter
dropped mean receptor luminance from 0.5338 to 0.2984, a 44% darkening with
1,147 of 3,335 receptors changing and some going nearly black. Mean drive moved
27.962 to 27.166. **2.8%.**

`engine.py` already said it: "This is NOT a calibrated phototransduction or
light-adaptation model."

**The fix.** `connectome_sim/photoreceptor.py` gains `adapted_drive`, and the
four places that computed the formula inline -- `engine.py`, `native.py`,
`gpu.py`, `physiology/brain.py` -- now call it. The semisaturation follows a
slow per-receptor running mean of luminance (500 ms, long relative to the 33 ms
frame interval so a passing object moves the response rather than being absorbed
into the operating point), floored at the original 0.02 so darkness cannot
divide it away. A receptor sitting at ambient now gives half its maximum current
and the steepest available response to change.

**On by default**, per instruction. `retinal_adaptation_ms=None` restores the
fixed constant exactly. 28 engine tests pass. Note that visual results recorded
before this are not comparable: with adaptation the receptors sit near 15 mV
rather than pinned near 28, so absolute spike counts drop by roughly half while
the *modulation* rises.

**Result, swatter present versus absent, no current injected anywhere:**

| population | fixed K | adaptive K | factor |
| --- | ---: | ---: | ---: |
| photoreceptor | 12,682 | 51,230 | **4.0x** |
| lamina | 1,181 | 9,605 | **8.1x** |
| visual projection | 1 | 7 | 7.0x |
| descending | 5 | 3 | 0.6x |
| LPLC2 / LC4 / LC6 / LPLC1 | 0 | 0 | -- |
| DNp01 | 0 | 0 | -- |

**It works, and it is not sufficient.** Four to eight times more signal survives
the first two stages. The looming detectors are still at exactly zero and the
giant fibre never fires.

**What that relocates.** The visual projection layer is the wall, not the
transfer function. 9,201 visual projection cells produce about 770 spikes across
200 ticks in every condition -- roughly 0.0004 spikes per cell per tick, which
is silence whatever arrives at them. Light adaptation was a real defect and
fixing it was necessary; the remaining failure is that lamina output does not
drive visual projection neurons in this model at all.

**Next:** characterise the stimulus in the fly's own visual field (angular size
and expansion rate at the ommatidia, and the dorsal coverage of the retina
mapping) before concluding anything about the escape circuit, and measure what
lamina drive a visual projection neuron would actually need to fire.

---

## 2026-09-20 — A fly swatter descends on the fly; the looming detectors never fire

**Asked:** add a swatter model, drive it at the fly, see how the fly responds.

**Why it should work.** The connectome contains the entire canonical escape
pathway: LPLC2 (185 cells), LC4 (126), LC6 (124) and LPLC1 (134) converging on
the giant fibre DNp01 (2 cells), with GFC1–GFC4 alongside. In a real fly an
approaching object drives LPLC2 and LC4, the giant fibre fires, the animal takes
off. All of it is present here and none of it had ever been shown an approaching
object.

**Ran:** `assets/Fly Swatter.STL` (157 x 91 x 9.5 mm, a real swatter against a
3 mm fly) added as a mocap body in `fly/body.py` behind `swatter=True`, so the
approach is prescribed and the swatter's own dynamics stay out of the result.
`fly/swat.py` drives it from 60 mm to 3 mm over 200 ticks at constant closing
speed, which gives the accelerating angular expansion looming detectors respond
to. Conditions: `live`, `frozen` (swatter descends, retina frozen at tick 0) and
`absent`.

**First result, with the leg/body motor loop running: everything silent.**
LPLC2, LC4, LC6, LPLC1, DNp01 and GFC1 all exactly zero across 200 ticks, in
both live and frozen. Live and frozen were also indistinguishable downstream:
descending 81,264 vs 81,090, DLM 5,860 vs 5,707.

That run was confounded. The motor loop's injected current holds the network at
**58,920 spikes/tick against a 21,349 resting rate** — the saturated regime
characterised elsewhere in this project. A looming response cannot be looked for
inside it.

**Re-run with no motor injection at all** (`--no-motor`), network at rest,
vision the only input. This is where the answer is:

| population | swatter | no swatter | difference |
| --- | ---: | ---: | ---: |
| photoreceptor | 2,788,725 | 2,801,407 | **-12,682** (-0.45%) |
| lamina | 1,125,643 | 1,124,462 | +1,181 (+0.11%) |
| visual projection (9,201 cells) | 828 | 829 | **-1** |
| descending | 911 | 916 | -5 |
| LPLC2 / LC4 / LC6 / LPLC1 | 0 | 0 | 0 |
| DNp01 (giant fibre) | 0 | 0 | 0 |
| VNC motor / DLM | 0 | 0 | 0 |

**The retina sees the swatter.** A dark 91 mm paddle descending overhead
occludes light, and the photoreceptor population registers 12,682 fewer spikes
because of it. That is a real, measured visual signal.

**Nothing downstream hears about it.** By the visual projection layer the
difference is one spike. The looming detectors never fire at all — not weakly,
not late, zero across 200 ticks in every condition. 9,201 visual projection
cells produce 828 spikes in total over the whole run, which is silence.

**Conclusion.** The fly does not respond to the swatter, and the reason is not
that the stimulus is absent or that the escape circuit is missing. The signal
dies between the lamina and the visual projection neurons. This sharpens the
earlier finding that "vision reaches the descending neurons and stops": at rest,
with no injected current anywhere, vision barely reaches the *visual projection*
neurons either.

**Caveat on the negative.** A stronger claim would need the stimulus
characterised in the fly's own visual field — angular size and expansion rate at
the ommatidia, not just object distance — and the dorsal coverage of this
retina mapping checked. The swatter is directly overhead; if the modelled
ommatidia have little dorsal field, a real fly would see more of this approach
than this model can. That is the next thing to check before calling the escape
pathway unreachable.

---

## 2026-09-20 — A closed leg loop, and a control that cut the wrong half

**Asked:** map leg inputs and outputs naively, for a closed but imperfect loop.

**Ran:** `fly/legs.py` and `fly/walk.py`. Ground contact and joint deviation
inject current into leg afferents; leg motor-neuron rates set leg joint targets.
42 driven actuators across six legs.

**First claim, wrong.** Compared against an **open-loop** arm that sensed and ran
the brain but never wrote the actuators: 4.10 mm of thorax displacement against
0.012 mm, a factor of 340. That control is nearly tautological -- it shows that
writing actuators moves the body, which was never in question. The claim was that
*sensing* drove the motion, and the control cut the motor path instead.

**Re-run with the right controls**, motor path connected throughout, 200 ticks,
motor gain 5:

| condition | sensory input | motor spikes | displacement |
| --- | --- | ---: | ---: |
| closed | live | 10,284 | 4.1644 mm |
| **frozen sense** | **held at tick 0** | **10,477** | **4.1829 mm** |
| no sense | none | **0** | 0.0505 mm |

Freezing the input is indistinguishable from live input, 0.4% apart, with
slightly *more* motor spiking in the frozen arm. With no injection the leg motor
neurons are silent. **This is a constant open-loop drive, not a closed loop.**

**Why the sensing does nothing.** The tactile channel is `8*tanh(force)` and a
standing fly's contact force is deep in tanh's flat region, so it sits pinned
between 7.107 and 8.000 (std 0.437) whether or not a leg is loaded. The
proprioceptive channel spans 0-1.469 mV against a rheobase near 7, so alone it
can never make a cell fire. One nearly constant current with no dynamic range --
the same failure mode as the visual transfer function found later the same day.

**Two bugs that failed silently**, both producing a running, plausible-looking
loop with missing inputs: contact sensors are registered *unprefixed* while
actuators carry the fly name, so the first lookup found zero sensors; and the
sided-instance split gave tactile afferents 1 cell per leg out of 213 until the
unsided remainder was dealt across both sides.

**Also ran:** `fly/babble.py`, sparse random current across the 19 sensory
subclasses with input/output logged per tick, as a dataset for fitting which
inputs move which outputs rather than guessing the next drive point. DLM fired
at ~22 spikes/tick under random sensory injection, where retinal input alone
leaves the entire 708-cell VNC motor pool silent.

**Rule carried forward:** cut the thing you are claiming does the work. A control
on the wrong side of a loop is worse than none, because it comes with a number.

---

## 2026-09-20 — Motor coverage extended to halteres, abdomen and neck; the halteres finally move

**Asked:** continue mapping VNC motor neurons onto the body, beyond the legs.

**Ran:** `fly/motor.py`, a map for the motor subclasses with a body part to
move, wired into `fly/walk.py` behind `--body`.

| subclass | cells | driven | target |
| --- | ---: | ---: | --- |
| leg (fl/ml/hl) | 381 | 328 | 42 leg joint actuators (`fly/legs.py`) |
| abdomen (ad) | 214 | 158 | 14 abdominal yaw/pitch actuators |
| neck (nm) | 24 | 24 | head yaw and pitch |
| haltere (hm) | 16 | 16 | the two haltere pitch actuators |
| wing (wm) | 67 | 0 | already driven by `fly.controls`' decode |
| other (xm) | 6 | 0 | bare identifiers, no body part identified |

That is **526 of 708 motor neurons** and **60 of 110 actuators**. The 53
undriven leg cells are the types with bare identifiers (`MNhl65`); the 49
undriven abdominal cells are neuromeres A8–A10, which are genital segments this
model's abdomen does not have. Both are dropped rather than folded into the
nearest joint.

Grounded in the reconstruction: subclass gives the body region, `somaSide` gives
L/R for all of them, and `somaNeuromere` gives the abdominal segment A1–A10,
which lines up directly with the model's abdomen1–7 chain. Inferred: that a
bilateral sum drives a pitch-like DOF and a left-minus-right difference drives a
yaw-like one. Head roll is left undriven because nothing separates it from yaw.

**The halteres move for the first time.** This entry's predecessor recorded them
at **3e-06 rad** over 44 wingbeats, because nothing ever commanded them. Driven
from their own 16 `hm` motor neurons:

| condition | haltere excursion | motor spikes | thorax displacement |
| --- | ---: | ---: | ---: |
| closed (live sense) | 5.033e-04 rad | 10,221 | 2.6083 mm |
| frozen sense | 5.012e-04 rad | 10,384 | 2.8063 mm |
| no sense | 8.734e-08 rad | 0 | 0.0389 mm |

168x the previously recorded excursion, and 5,700x the undriven arm here. Four
of the seven `hm` types are named for real haltere muscles — `hDVM MN` is the
dorsoventral power muscle, `hi1`, `hi2` and `hiii2` are steering muscles — so
the side assignment is read from the data, not chosen.

**But the sensing still contributes nothing.** Freezing the sensory input at its
first-tick value gives 5.012e-04 rad against the live arm's 5.033e-04, a 0.4%
difference, exactly as it did for the legs. With no injection the motor neurons
are silent and the halteres return to 8.7e-08 rad. So this is a constant
open-loop drive that happens to reach more of the body, not feedback.

**What it changes.** 0.0005 rad is about 0.03 degrees, nowhere near a real
haltere's beat, and the halteres still do not counter-oscillate with the wings.
The `--haltere-gain` pathway remains inert for the reason previously recorded:
tethered, the thorax is welded, and there are no sensors on the halteres to read
deflection from. What has changed is that the actuators are no longer
uncommanded, which was the first of the three steps this log listed for wiring
them properly.

**Caveat carried forward:** `--body` is off by default so leg-only runs stay
comparable with earlier entries.

---

## 2026-09-19 — Upstream flybody does not fly either, and that was the premise

Ran upstream flybody directly: its own XML, its own centimetre units, its own
`Flying` configuration (gain 18, stiffness 0.01, damping 0.00777, ellipsoid
fluid with `fluidcoef` including the 1.7 Kutta term), driven by its own WPG with
the measured pattern. dm_control 1.0.41 is incompatible with mujoco 3.9
(`flex_bandwidth`), so the model was loaded through `MjSpec` and configured by
hand instead.

**Force-array measure:** lift/weight = **+0.0069**, against our best of +0.0062.
Indistinguishable.

**Model-independent measure**, gravity on, 300 ms free fall:

| upstream, 300 ms | fall | % of free-fall |
| --- | --- | --- |
| **wings still** | 22.40 cm | **50.7%** |
| **flapping + ellipsoid fluid** | 22.87 cm | **51.8%** |
| flapping, no ellipsoid fluid | 27.93 cm | 63.3% |

**Flapping is marginally worse than holding the wings still.** The ~50%
reduction from free-fall is body drag; the wings contribute nothing upward. With
gravity zeroed the net vertical acceleration is -0.026 g — no lift at all, and
the apparent "support" under gravity is velocity-dependent drag.

**The project's premise was wrong.** The plan states that "the WPG keeps the fly
airborne on its own, so a fly whose connectome output is entirely disconnected
will still fly", and builds the vision control on top of that. It does not. The
WPG supplies a base oscillation; **lift comes from the learned policy's wing
offsets**, which is why flybody ships `trained-fly-policies.zip`. Flight in this
model is a control problem, not a property of the pattern.

**Consequences.**

* "The fly does not fly" was never a port bug. Every parameter search here was
  chasing a fault that is not in our code.
* Our port does still have two real defects worth fixing for fidelity: the
  ellipsoid fluid model is never enabled (so the wings have no Kutta lift term
  at all), and the cm->mm conversion of wing gain and damping was not applied
  where the stiffness conversion was.
* A connectome-driven fly cannot be expected to fly by decoding steering offsets
  onto a pattern that does not itself fly. Either a trained controller supplies
  weight support and the connectome perturbs it, or flight has to be learned —
  and the latter is a much larger project than this repo assumes.
* The README's flight claims and the plan's verification step 6 both need
  correcting. They are written on the assumption that flapping keeps the fly up.

---

## 2026-09-19 — Flight: four causes ruled out, still no lift

Continuing from the wing-pattern result below. Each row uses the measured
figshare pattern; lift is the `--hover` protocol (gravity zeroed, whole beats).

| configuration | tracking yaw/roll/pitch | lift / weight | peak |
| --- | --- | --- | --- |
| flygym as-is | 2.26 / 1.16 / 0.94 | -0.0174 | 4.05 |
| best of a 12-point gain x damping sweep | 1.29 / 1.00 / 0.99 | **+0.0062** | — |
| + ellipsoid fluid, upstream fluidcoef | 2.11 / 0.97 / 0.94 | -0.0006 | 9.71 |
| upstream params **as written** (gain 18) | 0.11 / 0.06 / 0.11 | +0.0002 | 0.01 |
| upstream params **converted cm->mm** (gain 1800) | 0.99 / 0.82 / 0.88 | -0.0052 | 0.38 |
| converted + ellipsoid fluid | 0.98 / 0.83 / 0.87 | -0.0113 | 2.41 |
| gain 3600 + ellipsoid (best tracking) | **1.03 / 1.02 / 1.07** | -0.0043 | 3.43 |

**Ruled out: the wing pattern, servo tracking, actuator gain/stiffness/damping,
and the ellipsoid fluid model.** Every one changes force *magnitude* — peak
ranges from 0.38 to 9.71 body weights across the table — and none produces net
lift. A fly needs 1.0; the best result anywhere is +0.006.

**What upstream actually does** (`flybody/tasks/base.py:270-322`), which flygym's
FlyBody never receives: wing gain 18, stiffness 0.01, damping 0.00777, and
`geom.fluidshape = 'ellipsoid'` with `fluidcoef = [1.0, 0.5, 1.5, 1.7, 1.0]` on
every `*fluid*` geom. `fluidcoef[3] = 1.7` is the Kutta lift coefficient, so
without that assignment the wings have drag and no lift term at all. FlyGym ships
the FlyBody rigged but not configured for flight.

**Another cm/mm trap.** Upstream is in centimetres and torque scales x100, so
gain 18 means 1800 in flygym's millimetre model and damping 0.00777 means 0.777.
Applied as written they collapse tracking to 0.10. FlyGym converted the joint
stiffness (0.01 x 100 = 1.0, which is what it ships) and not the rest — the same
partial-conversion pattern as the fluid medium.

**Still untested, and now the leading suspects.** Both are geometric rather than
parametric, which fits a failure that survives every magnitude change:

1. The re-added wing fluid ellipsoid's *orientation*. `fly/wing_fluid.py` copies
   quaternions verbatim from upstream's XML, but flygym's wing body frame may
   not match upstream's, in which case the lift vector points somewhere useless.
2. Whether flygym's yaw/roll/pitch joint axes are the axes the recorded pattern
   was authored against. Commanded ranges match the pattern exactly, which
   confirms the WPG is faithful but says nothing about whether flygym's "yaw" is
   upstream's "yaw".

**The decisive experiment is to run upstream flybody itself.** It is checked out
at `~/code/playground/drosophila/flybody`. If its own flight task produces lift
with this pattern, our port is broken and the diff localises it; if it does not,
the premise that this model flies in MuJoCo is wrong and the whole flight goal
needs rethinking. That separates the two possibilities in one run and should
come before any further parameter search here.

---

## 2026-09-19 — The measured wing pattern does not fix flight (`fly/render.py --wing-pattern`)

Downloaded `datasets_flight-imitation.zip` (12.9 MB, md5 verified) from the
flybody figshare record; it contains `wing_pattern_fmech.npy`, shape (500, 3),
the measured base wing kinematics. Vendored to `assets/`.

| | lift / weight | peak / weight |
| --- | --- | --- |
| bare sine | -0.0177 | 4.17 |
| **measured pattern** | **-0.0158** | 4.51 |

**No change.** The flight write-up named the bare sine as the cause of zero lift
and explicitly labelled that an inference by elimination rather than a
measurement. It has now been measured, and it was wrong.

**A better candidate: the wing servo overshoots.** Commanded against achieved
joint range, driven with the measured pattern at 218 Hz:

| dof | commanded | achieved | ratio |
| --- | --- | --- | --- |
| yaw (the stroke) | -0.84 .. +1.41 | **-2.32 .. +2.74** | **2.26** |
| roll | -0.32 .. +0.15 | -0.40 .. +0.15 | 1.16 |
| pitch | -0.56 .. +2.14 | -0.61 .. +1.93 | 0.94 |

FlyGym drives the wings with position actuators at gain 300/200/100; upstream
flybody uses gain 18 with the spring and damping in `_WING_PARAMS`. At 218 Hz
that servo rings and the wing sweeps 2.26x further than commanded, so the stroke
kinematics are wrong regardless of which base pattern is supplied — which is
why swapping the sine for the measured data changed nothing. Lift depends on the
yaw/pitch phase relationship within the stroke, and that relationship is being
distorted by the actuator, not by the pattern.

Next: bring achieved into line with commanded (lower the yaw gain, or move to
force actuators with upstream's spring/damping) and re-measure lift. Until the
servo tracks, no pattern experiment means anything.

**A methodology slip worth recording.** The first comparison returned identical
numbers to four decimals for both patterns, because the `--wing-pattern` flag
never reached `render()`: a string replacement missed its target and dropped the
argument silently. Caught only because identical-to-four-decimals is
implausible. The report now echoes which pattern was used, so a dropped argument
is visible in the output rather than inferable from suspicious agreement.

---

## 2026-09-19 — Leave-one-out refutes the seven-cell claim (`haltere_leave_one_out.py`)

**198 individually-silent afferents are not collectively silent.**

| set | n | 8 mV | 14 mV | 20 mV |
| --- | --- | --- | --- | --- |
| all_205 | 205 | 1061 | 653 | 597 |
| potent_7 | 7 | 894 | 895 | 1022 |
| **silent_198** | 198 | **892** | 724 | 634 |

Each of those 198 cells produces zero motor spikes driven alone; together they
produce as much as the seven potent ones. Sub-threshold summation dominates, and
the "interface is seven cells" conclusion from the single-cell sweep is
**withdrawn**. This was the caveat recorded with that result, and testing it was
the right call.

**What survives, and is strengthened: the pathway is one-dimensional.** The
response pattern of `silent_198` and `potent_7` are the same vector — cosine
0.9999, 0.9996, 0.9987 at 8/14/20 mV — symmetric power muscles, essentially
nothing on b1, b2 or hg1. So it is not that a few cells work; it is that every
subset does the same thing. Three independent subsets now support that, rather
than one analysis of seven cells.

Two further facts: the pathway is **strongly sub-additive** (all_205 = 1061
against potent + silent = 1786, ratio 0.59, falling to 0.36 at 20 mV), and
**non-monotonic in current** (1061 -> 653 -> 597), the effect `AGENTS.md` warns
about, now visible directly.

**Consequence for the joystick.** A multi-axis haltere interface cannot be built
from afferent identity in MaleCNS v1.0 — not because the right cells are
undiscovered, but because every subset drives the same single output mode. The
scalar `norm(omega)` in `proprioceptive_stimulation` is not an approximation to
be improved; it is the true dimensionality of this pathway. If multi-axis
information exists, it has to be carried by timing rather than identity, which
is what the tau = 2 ms result opens.

---

## 2026-09-19 — Single-cell sweep: the interface is seven cells (`haltere_single_cell.py`)

**Superseded by the leave-one-out result above: the seven-cell framing is an
artifact of testing cells one at a time.** The concentration measurement below
is still accurate as stated — it is the conclusion drawn from it that was wrong.

**198 of 205 haltere afferents produce exactly zero motor spikes when driven
alone at 20 mV.** Gini 0.976; the top five cells account for 93% of all
single-cell response and the top ten for 100%.

| body_id | type | side | out-deg | 8 mV | 14 mV | 20 mV |
| --- | --- | --- | --- | --- | --- | --- |
| 101048 | SApp | R | 293 | 0 | 0 | 1037 |
| 136883 | SApp | L | 311 | 0 | 0 | 1018 |
| **946174** | SNpp12 | R | 310 | **611** | 861 | 964 |
| 808963 | SNpp23 | L | 112 | 0 | 0 | 934 |
| 809889 | SNpp23 | R | 107 | 0 | 0 | 479 |
| 801205 | SNpp12 | L | 328 | 3 | 13 | 240 |
| 810009 | SNpp23 | L | 101 | 0 | 0 | 92 |

Every cell of SNpp14, 15, 20, 21, 25, 34, 35 and SNxx25 is individually silent —
45 cells, zero response between them. The 148-cell SApp bulk contributes through
two cells (Gini 0.987 within the type).

**Not a threshold artifact.** Two cells respond at 8 mV and seven at 20 mV:
raising the current fivefold recruits five more cells, not hundreds. And 946174
is uniquely low-threshold, firing 611 spikes at 8 mV where every other cell in
the graph gives 0 or 3.

**It closes the SNpp23 anomaly.** Its left cells total 1,026 spikes against 479
on the right. That 2:1 asymmetry is why antiphase drive failed to cancel for
SNpp23 in the depth-phase run while cancelling for every other pair — predicted
there, confirmed here by an independent measurement.

**What it costs.** The 45-pair antagonist sweep was mostly pairing objects that
cannot respond at all: only pairs containing SNpp12 or SNpp23 could do anything,
which is exactly the pattern observed. "Cluster" is the wrong unit, and the
usable haltere interface for a joystick is about seven named cells, not 205 or
ten clusters.

**The caveat that is not yet tested.** Silent *alone* is not the same as
contributing nothing *in combination*: sub-threshold inputs can sum at a shared
target. The cluster results are consistent with the potent cell dominating
(SNpp12 as a cluster gives 611 at 8 mV, exactly its R cell alone), but additive
sub-threshold contribution has not been measured and would need a leave-one-out
design to rule in or out.

---

## 2026-09-19 — Is the first synapse a bottleneck or a feature? (`haltere_tau_test.py`)

**A simulation bottleneck, and the fix has an optimum rather than a direction.**

| tau_m | corner | afferents z | hop-1 z | motor z | afferent rate |
| --- | --- | --- | --- | --- | --- |
| 20 ms (reference) | 8 Hz | 5.11 | **-0.28** | -1.12 | 43 Hz/cell |
| 5 ms | 31.8 Hz | 2.39 | 0.22 | -0.46 | 138 Hz/cell |
| **2 ms** | 79.6 Hz | **11.83** | **5.25** | **3.08** | **219 Hz/cell** |
| 0.73 ms | 218 Hz | 1.31 | 0.31 | 0.58 | 344 Hz/cell |

At tau_m = 2 ms the 218 Hz carrier crosses the first synapse and reaches the wing
motor pool. The wiring does not discard it; the membrane constant does. The
structural argument agreed in advance: convergence onto hop-1 cells is modest
(median 4 afferents each), every synapse carries the same fixed 1.8 ms delay,
and hop 1 is 100% excitatory, so afferents driven in phase spike synchronously
and their inputs arrive synchronously — summation preserves phase and nothing
structural is available to destroy it.

**Locking peaks where firing rate matches the carrier.** At tau = 2 ms the
afferents fire 219 Hz against a 218 Hz drive: one spike per cycle, the ideal
condition. At 0.73 ms they fire 344 Hz — more than one spike per cycle, so
spikes land at several phases and locking dilutes, with the 2.2 ms refractory
ceiling at 455 Hz. At 20 ms they fire 43 Hz, one spike per five cycles. So
"faster tau" is not the intervention; there is an optimum, and it moves with
drive level, since saturation depends on how hard the cells are driven. A
fast-tau subnetwork should be tuned so its relay cells fire near wingbeat
frequency, not as fast as possible.

**This run is the second attempt; the first was void.** See the bug below.

---

## 2026-09-19 — A bug I introduced, and what it invalidated

`Brain.step` gained a `stimulation` argument in the morning's tau commit, and it
injected the current without adding those cells to the active set. The engine
only integrates active cells, and that set is seeded with retina/lamina/sugar
alone — so injected current into any sensory afferent was silently ignored until
some synapse happened to recruit the cell. `kernel.cpp:26` awakens any cell
whose drive changed; the numba path did not.

Measured on 205 haltere afferents at 12 mV for 100 ms: **native fired 829 of
them, numba fired 1.** After the fix both fire 829 (totals 37,466 against
37,469 — close, not identical).

**Invalidated:** the first tau sweep, which ran on the numba backend. Its two
anomalies were both symptoms — zero spikes at tau = 0.73 ms, and a
non-monotonic dip at tau = 5 ms — which is why they were worth chasing instead
of explaining away. **Unaffected:** every other experiment in this log, all of
which used `NativeBrain`.

**Nothing to upstream.** `stimulation` did not exist on the numba `Brain.step`
before that commit, so doomfly cannot have the bug; every path there that
injects current goes through the correct C++ kernel.

**Worth keeping:** the two backends now agree to 3 spikes in 37,466 on an
identical stimulated run. That comparison would have caught this immediately had
it been run when the parameter was added.

---

## 2026-09-19 — 218 Hz by depth (`haltere_depth_phase.py`)

**The bottleneck is the first synapse, not the afferents.** Every cluster
phase-locks to a 218 Hz drive in its own spike train; not one passes it on.

| cluster | 218 Hz depth0 | depth1 | 10 Hz depth0 | depth1 |
| --- | --- | --- | --- | --- |
| pooled_all | 27.77 | **0.27** | 14.69 | 5.42 |
| SApp | 14.12 | **0.84** | 25.64 | 13.05 |
| SNpp12 | 6.97 | **-0.89** | 6.20 | 1.88 |
| SNpp23 | 42.04 | **0.20** | 7.73 | 2.02 |
| SNpp20 | 26.15 | — | 2.10 | — |

At 10 Hz the first synapse passes roughly half the locking (25.64 -> 13.05). At
218 Hz it passes none, in every cluster, including SNpp23's z = 42 collapsing to
0.2. This is the sharpest localisation of the problem so far, and it names the
intervention: the ~1,443 hop-1 relay cells are where a faster membrane constant
would have to go, not the afferents.

**An anomaly worth following: SNpp23 antiphase does not cancel** (depth0 z =
25.7, against 0.15 for pooled_all, -0.33 for SNpp12, 1.07 for SApp). Antiphase
cancellation in a pooled L+R readout requires the two sides to contribute
equally. SNpp23's three left and three right cells evidently do not — the same
class of asymmetry found inside SNpp12, where one of two cells carried the whole
cluster.

`SNpp20` shows `None` at depths 1 and 3: no spikes at all in those readouts,
consistent with its silence in the DC sweep.

**Method note.** The depth-2 column is uninterpretable — see below — and the
motor column reproduced the standalone phase experiment to the digit (4.61),
which is a useful agreement between two separately written scripts.

Reads out at four depths (stimulated afferents, hop-1 targets, hop-2 targets,
wing motor) rather than only at the motor pool, so a 218 Hz null says *where*
the modulation dies rather than only that it is absent. Depth 0 is a built-in
positive control: modulation is present in the stimulated cells by construction.
Every cluster also runs at 10 Hz, because a cluster-level null at 218 Hz is
uninterpretable on its own — single clusters showed nothing even at 10 Hz where
the pathway demonstrably follows.

**A readout flaw found in the first row, recorded before the rest arrives.**

    pooled_all 10 Hz in_phase   depth0: 14.69  depth1: 5.42  depth2: -0.31  motor: 4.61

Depth 2 pools ~60,000 cells into one spike train. They sit at different path
lengths, so their modulation arrives at different phases and cancels in the sum:
the pooled trace reads as chance even if every constituent cell is modulated.
**The depth-2 column is not interpretable** and the meaningful comparison is
depth 0 → depth 1 → motor. Fixing it properly would mean per-cell vector
strength averaged over cells, not vector strength of the pooled train.

The rest is sound: depth 0 confirms the drive, the first synapse attenuates
~3×, and the motor value reproduces the standalone phase experiment exactly
(4.61 under identical conditions), which is a useful consistency check between
two separately written scripts.

---

## 2026-09-19 — Johnston's organ, first pass (`jo_tracing_check.py`, `jo_potency.py`)

**A claim checked and rejected before building on it.** A suggestion arrived that
linear acceleration, gravity and wind should be read from the JO-A array
(JO-A1–A4). MaleCNS's own `subclass` labels say the opposite: JO-A is
**auditory 49 cells to 1**, while the wind/gravity population is JO-E (EV 176,
ED 91) and JO-C (CL 19, CM 23). That matches Kamikouchi et al. 2009 and Yorozu
et al. 2009 — JO-A/B are the phasic sound-and-vibration subgroups, JO-C/E the
tonic ones responding to sustained deflection. JO-A1–A4 is also only 26 cells.
Driving JO-A for gravity would have driven the auditory pathway.

**Tracing check first, because all 672 JO cells are `RT Hard to trace`** — the
dataset's lowest tier, with no Reviewed subset to stratify against. Structural
proxies instead, against the haltere afferents as a positive reference:

| population | n | median out-degree | zero-output |
| --- | --- | --- | --- |
| JO wind_gravity | 475 | 86.0 | 57 (12%) |
| JO auditory | 114 | 38.5 | 29 (25%) |
| haltere afferents | 205 | 114.0 | 1 (0.5%) |
| whole graph | 166,700 | 112.0 | 1,220 (0.7%) |

Type labels are structurally real — within-type target overlap 0.097 against
0.024 between types, a ratio of **3.99**, matching the haltere reference's 3.80.
But ~13% of wind_gravity cells are dead ends and arbors are truncated, so
**every potency result is a lower bound**: silence cannot be distinguished from
an unreconstructed axon. And bilateral pairing is unavailable — median L/R
imbalance 0.472, with 16 of 34 types worse than 2:1 — so the haltere design's
reliance on types being near-perfect bilateral pairs does not port.

**The control came back and the wind/gravity result does not survive it.**
Size-matched random draws from other sensory populations (`jo_specificity_control.py`),
at 8 mV, 3 draws each:

| random n | draws | JO group at that size | JO 8 mV | verdict |
| --- | --- | --- | --- | --- |
| 19 | 0, 0, 0 | JO-FD (8) | 2055 | **specific** |
| 19 | 0, 0, 0 | JO-mz (11) | 2865 | **specific** |
| 19 | 0, 0, 0 | JO-CM (30) | 2404 | **specific** |
| 50 | 184, 0, 0 | JO-A (50) | 2121 | **specific** |
| 50 | 184, 0, 0 | JO-FV (70) | 3116 | **specific** |
| 91 | 916, 3903, 0 | JO-ED (91) | 2192 | within random |
| 176 | 2787, 3437, 3537 | JO-EV (176) | 3173 | **within random** |
| 475 | 3507, 3857, 4772 | pooled_wind_gravity (475) | 3498 | **within random** |

JO-EV and pooled_wind_gravity -- the populations this whole line of work was
pointed at -- produce exactly what a random draw of the same size produces. At
n >= 176 the assay is saturated: injecting current into any 176 sensory cells
fills the motor pools, so there is no dynamic range left to distinguish JO from
anything. The earlier claim that "JO reaches the flight motor system harder than
the halteres do" was measuring saturation, not JO, and is withdrawn.

What *is* specific is small: JO-FD produces 2,055 spikes from **8 cells** where
random 19-cell draws give zero; JO-mz 2,865 from 11; JO-CM 2,404 from 30. And
JO-A -- the *auditory* array -- is specifically potent at 50 cells against a
random mean of 61.

Same shape as the halteres: potency concentrated in a few small groups, large
populations indistinguishable from generic ignition. The fix is to leave
saturation -- rerun the large arrays at 4-6 mV or shorter duration, where random
draws are silent and the assay has range.

**Original potency result, superseded by the control above.** Nearly every JO group
drives thousands of motor spikes at 8 mV (unstimulated baseline is 0 in every
pool). Output lands on abdomen (~1,750 spikes across 214 cells) and wing
(~1,400 across 67) — per cell the wing pool is the strongest target, stronger
than the halteres reach it — while neck, the classic gravity/wind postural
output, gets 5–87 spikes across 24 cells.

| group | n | abdomen | wing | legs f/m/h | neck | 8→20 mV |
| --- | --- | --- | --- | --- | --- | --- |
| JO-EV | 176 | 1198 | 1651 | 314/387/330 | 87 | 3173→4132 |
| JO-ED | 91 | 1472 | 1242 | 306/315/260 | 58 | 2192→3758 |
| JO-B | 88 | 1174 | 1096 | 135/257/230 | 48 | 699→3047 *graded* |
| JO-CL | 19 | 72 | 195 | 0/4/56 | 6 | 0→389 *graded* |
| JO-A (auditory) | 50 | 1145 | 1082 | 36/135/145 | 20 | 2121→2636 *flat* |
| pooled wind_gravity | 475 | 1755 | 1391 | 457/377/281 | 67 | 3498→4465 |

Two problems with reading this as "JO drives the motor pools".

**Most groups are flat in current** — JO-A goes 2121 → 2636 from 8 to 20 mV, and
CM, FD, FV, mz likewise. That is not the haltere signature (sharp threshold,
graded, only 2 of 10 clusters responding), and combined with haltere input
reaching 97% of the brain in three hops it suggests that injecting current into
any large population ignites the network generically. `jo_specificity_control.py`
tests exactly that with size-matched random draws from other sensory
populations; until it returns, this table says nothing specific about JO.
JO-B, CA and CL would survive that control regardless, being genuinely graded.

**An entire side of the auditory population is unreconstructed.**
`pooled_auditory_R` (52 cells, 27 with zero outputs) gives **exactly 0 at every
current** while `pooled_auditory_L` (62 cells, 2 zero-output) gives ~2,500.
`JO-unclear` (102 cells, 57 zero-output) is 0 throughout. An L/R comparison here
would read reconstruction damage as biology.

---

## 2026-09-19 — In-phase vs antiphase drive (`haltere_phase_pairs.py`)

**The pathway sums bilateral haltere input rather than comparing it.**

Two groups driven sinusoidally with a relative phase offset; total injected
current identical across phases, so any difference is a phase effect. 10 Hz is a
positive control (the MTF says the pathway follows there); 218 Hz is the
question.

| pair | 0° in-phase | 90° quadrature | 180° antiphase |
| --- | --- | --- | --- |
| all halteres L\|R @ 10 Hz | **z = 4.61** | z = 3.61 | **z = −0.56** |
| SNpp12\|SNpp23 @ 10 Hz | **z = 4.25** | z = 1.44 | **z = −0.52** |
| every pair @ 218 Hz | −0.76 … −0.05 | −1.16 … −0.37 | −0.74 … +0.15 |

Monotonic in phase offset, in two independent pairs: in-phase locks strongly,
quadrature partially, **antiphase not at all**. That is a cancellation
signature. The convergence point computes something like L+R, so a pitch-like
in-phase signal survives and a roll/yaw-like antiphase signal cancels to a DC
level carrying no modulation.

This is the mechanism behind the DC sweep's null. Antisymmetric drive did not
fail to produce a *lateralised* response; it fails to produce a *modulated* one
at all, because the two sides cancel where they converge. Symmetric power was
1.000 in all 24 trials regardless of drive phase.

At 218 Hz nothing, anywhere, as predicted from the 8 Hz corner. The prediction
was recorded before the run.

**Single small clusters show nothing at any phase** (SNpp12_L\|R, SNpp23_L\|R:
z from −0.4 to 1.02). The effect needs the full ~102-cell-per-side population;
one or three cells cannot modulate the pool detectably. So this is a population
result and does not license claims about individual clusters.

---

## 2026-09-19 — Modulation transfer function, corrected (`haltere_mtf.py`)

**Corner between 10 and 30 Hz; nothing above it in any readout.**

The first run reported per-group vector strength without per-group floors, and
I flagged the b1/b2 numbers (r of 0.25–0.63 even at 218 Hz) as uninterpretable.
They were. Each group now gets a chance level computed *within* the trial, from
the same spike train at frequencies it was not driven at, which scales with
spike count by construction.

| Hz | pooled r | pooled z | control z | power_L z | power_R z | b1/b2/hg1 z |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 0.156 | **5.3** | −0.0 | **5.6** | **5.4** | −2.5 … 1.9 |
| 10 | 0.144 | **4.6** | −0.6 | **4.7** | **4.0** | −0.3 … 2.3 |
| 30 | 0.026 | −0.2 | −1.4 | −0.1 | −0.9 | −1.8 … 1.3 |
| 60–400 | 0.015–0.051 | −1.2 … 0.8 | −1.3 … −0.4 | −0.7 … 0.4 | −1.3 … 1.5 |

The apparent fast following in the steering muscles was small-N artifact:
**b1_L, b1_R, b2_L and b2_R fire 5 spikes each** in a 1000 ms trial, and chance
vector strength at 5 spikes is ~1/sqrt(5) = 0.45 — exactly the range reported.
With proper floors, only the power muscles (886 and 907 spikes) lock, only at
5–10 Hz. The speculation that b1 might follow faster, and the Fayyazuddin &
Dickinson connection I hung on it, is **refuted**.

Corner matches 1/(2*pi*tau) = 8.0 Hz for tau = 20 ms, so the membrane constant
is the binding constraint, not the balanced convergence. Following a 218 Hz
wingbeat would need tau ~= 0.73 ms — shorter than the 1–5 ms of fast
interneurons, and worth putting beside Fox et al.'s measured 0.81 ms spike-timing
jitter in haltere afferents: the biology works at that timescale through precise
spike timing, not through an implausibly leaky membrane.

**Question.** Does a sinusoidal modulation of haltere drive reach the wing motor
pool, and up to what frequency? A wingbeat is 4.59 ms / 218 Hz.

**Why this and not the impulse test.** The impulse measurement below asked
whether a brief input *from rest* can drive firing. It cannot, but from rest the
threshold dominates and that says little about a flying animal. Here a
supra-threshold baseline (12 mV) holds the pool firing and the sinusoid is a
perturbation on top — ongoing activity linearises the threshold. This is the
regime a beating haltere actually produces.

**Metric.** Vector strength of binned wing-motor spikes at the modulation
frequency, each paired with an unmodulated control at the same baseline that
gives the chance floor. Sweep 5–400 Hz.

**Decides.** Whether lowering the membrane time constant is worth doing, and by
how much. Result pending.

---

## 2026-09-19 — Antagonist-pair sweep, corrected (`haltere_axis_pairs.py`)

**Question.** Do haltere clusters form antagonist pairs carrying a symmetric
(pitch-like) or antisymmetric (roll/yaw-like) signal? Four sign conditions per
candidate pair; conditions 3 and 4 are the sign-negations of 2 and 1, which is
the falsification test.

**Correction to the first run.** The first sweep used baseline 11 ± 3 mV, so its
"low" condition sat at 8 mV — *below* the 8–10 mV recruitment threshold that
flappy-haltere's cluster sweep had already measured. The four conditions were
on/off, not a sign flip. Rerun at 12 ± 2 (10 and 14, both supra-threshold).

**Result: no antagonist structure and no lateralisation.**

| | 11 ± 3 (confounded) | 12 ± 2 (corrected) |
| --- | --- | --- |
| silent pairs | 12/45 | 14/45 |
| pairs passing both criteria | 0 | 2, both noise (ref 15 and 21 spikes) |
| symmetry of the *antisymmetric* condition | ≈1.0 | min 0.851, mean 0.985 |

Across the 16 responsive pairs, antisymmetric drive produces a response that is
85–100% symmetric. Driving left hard and right weakly gives almost exactly the
same bilateral output as the reverse. Sign inversion also proved unreliable once
the confound was removed — the same pair gives `inv_sym = −0.997` and
`inv_anti = +0.997`, which tracks which cluster is driven harder rather than any
push/pull axis.

Every responsive pair contains SNpp12 or SNpp23; all 14 silent pairs contain
neither. Four pairs are byte-identical to another pair, meaning the second
cluster contributes nothing at all.

**Method bug found mid-run, worth keeping.** The first version computed sign
inversion as `cos(r1, −r4)` on raw spike counts. Counts are non-negative, so that
cosine can only land in [−1, 0] and was measuring whether two responses are
*parallel* — the opposite of the intent. Fixed by expressing every response as a
deviation from an all-groups-at-baseline reference. **+1 now means a passing
pair**; the protocol doc in flappy-haltere still says −1 and needs correcting.

---

## 2026-09-19 — Downstream trace (`haltere_downstream.py`)

**Question.** The pathway needs ~20 ms of drive before the motor pool fires.
Does haltere input converge onto progressively slower paths?

**Result: no — it diverges, and there are no slower cells to converge onto.**

| hop | new cells | cumulative | excitatory |
| --- | --- | --- | --- |
| 1 | 3,784 | 3,989 | **100%** |
| 2 | 60,400 | 64,389 | 53% |
| 3 | 98,051 | **162,440** | 56% |

By three synapses the signal has touched 97% of the 166,700 neurons. A single
2-cell cluster reaches 116,144 by hop 3. Every neuron in this model shares one
20 ms membrane constant, so cell identity cannot be what is slow. Hop 1 being
100% excitatory is a real structural fact and the expected one for cholinergic
afferents.

**What is actually slow: balanced convergence at the target.** The path to the
wing muscles is 1–2 synapses (1.8–3.6 ms), so delay explains nothing. But each
steering motor neuron is a *single cell* receiving 400–700 inputs of which
37–51% are inhibitory (power muscles: ~5,500 inputs, 33% inhibitory). A single
volley is cancelled; crossing threshold needs sustained excitation outpacing
balanced inhibition, which takes about one membrane time constant.

**Direct wiring is anti-predictive.** The five clusters reaching the motor pool
in one hop (SNpp14, 20, 25, 34, 35) are exactly the silent ones; both potent
clusters are two hops away. flappy-haltere had found direct wiring merely
unpredictive; it is worse than that.

---

## 2026-09-19 — Impulse response (`haltere_impulse.py`)

**Question.** Verify, rather than calculate, how much sub-wingbeat structure
survives to the motor pool. The prior claim was analytic: a 20 ms membrane
passes ~3.6% of a 218 Hz modulation.

**Result: a hard floor at ~4.4 wingbeats.**

| pulse | wingbeats | motor spikes | + 100 ms tail |
| --- | --- | --- | --- |
| 1, 2, 5, 10 ms | 0.2–2.2 | **0** | +0 |
| 20 ms | 4.4 | 3 | +182 |
| 100 ms | 21.8 | 56 | +239 |
| 500 ms | 109 | 653 | +241 |

Below ~20 ms of sustained drive the pool produces nothing at all — not a small
response, and not a delayed one. Stronger than the filtering argument it was run
to check: sub-wingbeat input does not produce an attenuated motor response, it
produces none. Once ignited the network rings >100 ms regardless of pulse length.

**Caveat noted at the time, and acted on.** This is the from-rest regime, where
threshold dominates. See the MTF entry above.

---

## 2026-09-19 — Device log and SNpp12 (Android `FlyMapActivity`)

Pulled 499 events from `design.antics.androsophila`. Whole session ran at
8.0 mV — below the recruitment threshold — so only SNpp12 did anything reliably
(24.2% of 62 touches; SNpp23 9.5%; every other cluster 0%).

**SNpp12 is one cell.** Stimulated alone, 500 ms from reset:

| cell | side | 8 mV | 10 mV | 12 mV | 14 mV |
| --- | --- | --- | --- | --- | --- |
| 801205 (idx 145211) | L | 3 | 108 | 9 | 13 |
| 946174 (idx 164845) | **R** | **611** | 848 | 893 | 861 |

The R cell carries essentially the whole cluster and is already supra-threshold
at 8 mV. The L cell is weak and non-monotonic, peaking at 10 mV — as
flappy-haltere's own targeted run had found.

**Its output is symmetric**, power_L 288 / power_R 290 at 8 mV, despite 2-hop
synapse counts favouring the right 138 to 89. Counted connectivity does not
predict which side fires, consistent with the divergence result.

**The device log's left-only pattern is an app artifact, not anatomy.** A clean
reset sim gives symmetric output and strong power-muscle firing; the device gave
`thorax_hz = 0` in all 62 SNpp12 rows and `wing_r_hz = 0` in all 499 rows of the
file. The app applies drive with decay (`decay ticks: 15`) against a live
never-reset brain, so it is a different protocol. This is the same reason
`inverse_data_device.py` re-simulates rather than using device readouts as
labels. No mid-decay contamination in this export (0 of 499 duplicate rows).

---

## 2026-09-18 — Does the fly fly? (`fly/render.py --hover`)

**No.** Net lift −0.023 body weights; `ellipsoid_fluid=True` gives +0.075 and no
wing fluid geoms gives −0.001. All zero. Peak in-beat force is ~4× body weight,
so the wings move plenty of air and a symmetric sine stroke cancels it over the
cycle. Cause is the bare-sine wing pattern — **inferred by elimination, not
measured**: the alternative (the measured figshare base pattern) has not been
run.

Lift measured with gravity zeroed, because a falling body sees an upward drag
indistinguishable from lift in `qfrc_passive`, tending to 1.0 at terminal
velocity. Averaged over whole wingbeats only; peak in-beat force exceeds the
mean by ~4×, so a partial beat biases the mean by more than the mean.

**Two bugs found on the way, either of which would have given a wrong answer.**
FlyGym ships the flybody fluid medium in centimetre units while the model is in
millimetres — 1000× too dense, denser than water. As shipped the fly sinks 2.8 mm
in 200 ms and looks nearly airborne. And the wingbeat was running at ~436 Hz
because the vendored WPG advances one 2e-4 s control step per call and was being
called every 1e-4 s physics step; only achieved wing amplitude reveals it.

---

## 2026-09-18 — Are the halteres wired up?

**No.** Bodies, joints, geoms and position actuators exist, but nothing commands
them: haltere qpos moves 3e-06 rad over 44 wingbeats, and the model has **zero
sensors** (`nsensor == 0`), so no Coriolis force is measured anywhere. The
connectome's 205 afferents are driven by an engineered scalar from thorax
angular velocity, which is identically zero while tethered.

Found a bug doing it: `_thorax_gyro` sliced `qvel[3:6]` as body angular velocity,
but `TetheredWorld` has no freejoint — those dofs are rostrum and haustellum
joints. The haltere afferents were being driven by the proboscis, and read zero
only because the mouthparts happened to be still.
