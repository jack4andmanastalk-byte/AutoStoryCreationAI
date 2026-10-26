# Plot memo ablation: t01-s1-seed0

- Scope: **Arena × L1 exploratory reference only**.
- Target: Plot-SKILL-derived memo handoff only; not overall SKILL efficacy.
- Task/system/seed: t01 / S1 / 0
- Model/version: arena-agent-mode / unversioned
- Draft temperature: 0.8
- Shared canon/design hashes: see `results.json`.
- L2/L3: `frozen_not_measured`; G5/reproducibility: not established by one pair.

| Arm | Chars (markers excluded) | Must-include rate | Task-avoid hits | Forbidden hits | Forbidden / 10k chars | CED / 10k chars |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_plot | 3343 | 1.0 | 0 | 0 | 0.0 | 20.207 |
| with_plot | 3374 | 1.0 | 0 | 0 | 0.0 | 12.447 |

## Limits

The intervention is the inclusion of chapter-local Plot memo lines. The first
chapter's prompts are checked for equality after removing those lines. Later
chapters may receive different prior-chapter text because prior outputs are
part of the pipeline; that is a downstream mediated effect, not an independently
controlled chapter-level effect. L1 indicators are reported separately and do
not measure interest, originality, or reader preference. This one paired run
cannot establish a general effect. No L2/L3 judgments were made.
