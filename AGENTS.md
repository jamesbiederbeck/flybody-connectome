# flybody-connectome constraints

- Vision does not reach the wing motor neurons in MaleCNS v1.0. Measured: all
  708 VNC motor neurons are silent under retinal drive while DNp20 and DNpe017
  fire. Do not "fix" this by wiring a shortcut and presenting it as connectome
  wiring. If a bridge from descending activity to the motor pool is added, it is
  an engineered bridge and must be labelled as one everywhere it appears.
- The haltere drive is host-side current injection before the audited kernel
  runs -- an engineered joystick, not modeled campaniform transduction. Same
  constraint as `flappy-haltere`. Its response is non-monotonic in current, so
  never assume more current means more flight, and always measure with a fresh
  brain per condition: reusing one across amplitudes carries state and produced
  a wrong answer once already.
- "It flapped" is not evidence of anything. The wingbeat pattern generator keeps
  the wings beating with the connectome disconnected. Every claim that vision
  reaches the wings must be backed by the `--frozen-vision` control, and the
  metric is steering asymmetry, not time aloft.
- Preserve negative results. The frozen-vision control currently matches the live
  run exactly because the arena is empty; that belongs in the README, not in a
  commit that quietly adds a scene and reports success.
- The ommatidia registration is a fit between a male connectome and a female
  micro-CT eye. Keep the residual and unmatched counts in the run report. If they
  get worse, that is a finding about the data, not a number to tune away.
- The connectome's eyes are lopsided (1,107 mapped receptors left, 2,228 right).
  Any left-minus-right signal inherits that bias. Do not attribute an asymmetric
  response to vision without ruling it out.
- Decoder gains in `controls.py` are engineering choices, not measurements. Say
  so wherever they are documented, and question them first when behaviour is odd.
- Do not modify `connectome_sim/`; it is a separate repository with its own
  constraints. Bump the submodule pointer instead.
- FlyGym's FlyBody support is experimental upstream. Pin the version, and treat
  `tests/test_fly_body.py` as the tripwire: it asserts nu/nq, the wing actuators,
  the eye cameras, the restored wing fluid geoms and the ommatidia shape.
- Getting "off the WPG" means replacing kinematic replay with a thorax resonance
  model, not driving wing position from per-spike DLM activity. *Drosophila* is
  an asynchronous flier; per-beat neural patterning would be less faithful, not
  more.
