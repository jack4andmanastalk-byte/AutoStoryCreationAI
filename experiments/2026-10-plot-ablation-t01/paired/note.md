# Plot memo ablation: t01-s1-seed0 — Arena responses pending

No experiment result has been produced yet. Each arm has its own operator directory; keep its tagged answers with the matching arm.
Combined pending prompt bundle: `/home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/PROMPTS.md`.

### shared_prep arm

Pending requests: 1. Copy `/home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/relay/t01-s1-seed0/shared_prep/relay/PROMPTS.md` to the Arena chat. Save its tagged answers and ingest them with:

`/home/user/AutoStoryCreationAI/.venv/bin/python scripts/relay_prompts.py ingest --dir /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/relay/t01-s1-seed0/shared_prep --file answers.txt --model arena-agent-mode --model-version unversioned`

After ingesting the answers, rerun the same command to continue (or pass `--ingest answers.txt --resume` to ingest across arms/stages and advance in one command):

```sh
/home/user/AutoStoryCreationAI/.venv/bin/python scripts/run_plot_ablation.py --id t01-s1-seed0 --task t01 --canon /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/inputs/canon --design-dir /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/inputs/design --prepare-shared --provider arena --seed 0 --temperature 0.8 --out /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired --runs-root /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/attempts --operator-root /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/relay --resume
# or in one step:
/home/user/AutoStoryCreationAI/.venv/bin/python scripts/run_plot_ablation.py --id t01-s1-seed0 --task t01 --canon /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/inputs/canon --design-dir /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/inputs/design --prepare-shared --provider arena --seed 0 --temperature 0.8 --out /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired --runs-root /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/attempts --operator-root /home/user/AutoStoryCreationAI/experiments/2026-10-plot-ablation-t01/paired/relay --resume --ingest answers.txt
```
