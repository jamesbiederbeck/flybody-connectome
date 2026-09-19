# Haltere experiments

Three runs, answering why the haltere pathway cannot carry a phase code in this
model and what is actually responsible.

## `haltere_impulse.py` — the pathway has a hard floor at ~4.4 wingbeats

Sustained drive at 14 mV into all 205 afferents, varying duration:

| pulse | wingbeats | wing-motor spikes | + 100 ms tail |
| --- | --- | --- | --- |
| 1, 2, 5, 10 ms | 0.2–2.2 | **0** | +0 |
| 20 ms | 4.4 | 3 | +182 |
| 50 ms | 10.9 | 16 | +157 |
| 100 ms | 21.8 | 56 | +239 |
| 500 ms | 109 | 653 | +241 |

Below ~20 ms of sustained drive the motor pool produces **nothing at all** — not
a weak response, and not a delayed one either (the 100 ms tail is empty too).
This is stronger than the analytic filtering argument it was run to check: a
20 ms membrane passes ~3.6% of a 218 Hz modulation, but 3.6% of nothing is the
wrong way to think about it. Sub-wingbeat structure does not produce a small
motor response, it produces no motor response.

Once ignited the network rings for >100 ms regardless of how long the pulse was,
which is the same slowness seen from the other end.

## `haltere_downstream.py` — divergence, not convergence

The intuition this was run to test was that haltere input converges onto
progressively slower paths. It does not, in two senses.

**It diverges.** New cells reached per hop from all 205 afferents:

| hop | synapses | new cells | cumulative | excitatory | reaches wing motor |
| --- | --- | --- | --- | --- | --- |
| 1 | 26,638 | 3,784 | 3,989 | **100%** | yes |
| 2 | 866,552 | 60,400 | 64,389 | 53% | |
| 3 | 13,048,430 | 98,051 | 162,440 | 56% | |
| 4 | 11,594,341 | 3,877 | 166,317 | 69% | |

By hop 3 the signal has touched 162,440 of 166,700 neurons — **97% of the
brain**. A single 2-cell cluster (`SNpp12`) reaches 116,144 new cells by hop 3.

**And there are no slower cells to converge onto.** Every neuron in this model
has the same 20 ms membrane and 5 ms synaptic constant; there is no fast/slow
population structure for the graph to reveal. Whatever is slow here is not cell
identity.

Hop 1 being 100% excitatory is a real structural fact, and the biologically
expected one for cholinergic sensory afferents. Inhibition first appears at
hop 2.

## What actually makes it slow: balanced input at the motor neuron

The path to the wing muscles is **short** — 1 or 2 synapses, i.e. 1.8–3.6 ms.
So delay does not explain a 20 ms floor. Convergence at the target does:

| readout | cells | presynaptic partners | inhibitory |
| --- | --- | --- | --- |
| b1_L / b1_R | 1 each | 446 / 452 | **51.3%** |
| b2_L / b2_R | 1 each | 650 / 678 | 41.4% / 43.1% |
| hg1_L / hg1_R | 1 each | 713 / 726 | 41.1% / 37.5% |
| power_L / power_R | 12 each | 5,603 / 5,373 | 32.6% / 33.4% |

Each steering motor neuron is a *single cell* receiving 400–700 inputs of which
roughly half are inhibitory. A single volley — even one arriving 3.6 ms after
the stimulus — is cancelled. Crossing threshold takes sustained excitation
outpacing balanced inhibition, and ~20 ms is how long that takes, which is
about one membrane time constant. The slowness is temporal summation against
balanced input, not a slow pathway.

## Direct wiring is anti-predictive here

Which clusters reach the wing motor pool in one hop, against which clusters
actually fire it:

| reaches wm at hop | clusters | drive the pool? |
| --- | --- | --- |
| 1 | SNpp14, SNpp20, SNpp25, SNpp34, SNpp35 | **none of them** |
| 2 | SNpp12, SNpp15, SNpp21, SNpp23, SNxx25 | SNpp12 and SNpp23 only |

flappy-haltere had already found that direct wiring does not *predict* effect.
It is worse than that: the five clusters with a one-hop line to the motor pool
are exactly the silent ones, and both potent clusters are two hops away.

## Consequence for the phase question

Each synapse costs 1.8 ms, which is 141° of phase at a 4.59 ms wingbeat, so
reaching the motor pool costs 141° or 283° depending on cluster — different
clusters arrive at different phases before anything else happens. That would
already scramble a phase code, and it is moot anyway given the 20 ms floor.

Lowering the membrane time constant is therefore necessary but not sufficient:
the ~450:1 convergence with ~50% inhibition would still demand summation. A
fast-τ run needs the operating point re-established and a positive control that
the pool responds to anything at all, or a null is uninterpretable.
