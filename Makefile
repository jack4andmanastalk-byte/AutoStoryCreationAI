PYTHON ?= python3
VENV    ?= .venv
BIN     := $(VENV)/bin
CONFIG  ?= configs/dataset.yaml
WORK    ?= 120
# skills/harness need PyYAML: prefer the virtualenv when it exists
RUN     := $(shell [ -x $(BIN)/python ] && echo $(BIN)/python || echo $(PYTHON))

.PHONY: help setup test data data-aozora data-narou pull-datasets report controls-propose research research-check audit evaluate experiment pilot-model blind-pairs plan design story story-s2 story-s3 baseline brief world history character relation plot scene voice revise branch adaptation calibrate gamelog-check two-stage probe-gamelog skills-check protocol-check ci clean distclean

help: ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## create the virtual environment and install the dependencies
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

test: ## run the unit tests
	$(BIN)/python -m pytest tests -q

data: data-aozora data-narou ## download every dataset (metadata + plain texts, no PDFs)

data-aozora: ## Aozora Bunko: bibliographic records and plain texts
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) aozora-metadata
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) aozora-texts --works $(WORK)

data-narou: ## Syosetsuka ni Narou: metadata, Top-300 + 5-genre supplement full-episode plain texts
	$(BIN)/python scripts/fetch_narou_api.py --config $(CONFIG) --per-query 500 --order-pages 4
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-metadata --cached-only
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-rank --top 300 --scan-limit 1100
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-texts --works 300 --max-episodes 0 --rank-order
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-genre-supplement --per-genre 15 --min-per-genre 10
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) purge-pdfs

pull-datasets: ## fetch prebuilt datasets and plain texts from the 'datasets' branch
	git fetch origin +refs/heads/datasets:refs/remotes/origin/datasets
	mkdir -p data
	git archive origin/datasets | tar -x -C data

report: ## print statistics about the generated datasets
	$(BIN)/python scripts/dataset_report.py --config $(CONFIG)

controls-propose: ## rank Aozora control-group candidates per task (needs data/)
	$(BIN)/python scripts/select_controls.py propose

research: ## rebuild the unified research catalog from research/curated
	$(PYTHON) scripts/build_research_catalog.py

research-check: ## verify the committed research catalog is up to date
	$(PYTHON) scripts/build_research_catalog.py --check

audit: ## audit the demo story against its canon (shows the 7 seeded defects)
	$(RUN) scripts/audit_continuity.py \
		--canon harness/cases/demo/canon --text harness/cases/demo/text \
		--out build/audit/demo.json --ledger build/audit/demo-ledger.json \
		--markdown build/audit/demo.md --fail-on none

evaluate: ## run the evaluation harness on the demo story (L1 + recorded L2)
	$(RUN) scripts/run_evaluation.py \
		--candidate harness/cases/demo/text --baseline harness/cases/demo-baseline/text \
		--canon harness/cases/demo/canon --patterns harness/patterns.yaml \
		--judge-fixture harness/fixtures/judgements-demo.json --out build/eval/demo \
		--report-only

story: ## run S1 end to end (plan -> design -> draft -> audit) with the scripted fixture
	$(RUN) scripts/run_pipeline.py --task t01 --out build/runs \
		--script benchmarks/protocol-v1/fixtures/plan-demo.json --report-only

design: ## validate the 8 design documents against a planned canon (scripted)
	rm -rf build/runs/design-demo-plan build/runs/design-demo
	$(RUN) scripts/run_pipeline.py --task t01 --system s1 --stage plan \
		--out build/runs --run-id design-demo-plan --report-only --quiet \
		--script benchmarks/protocol-v1/fixtures/plan-demo.json
	$(RUN) scripts/run_pipeline.py --task t01 --system s1 --stage design \
		--canon build/runs/design-demo-plan/canon --out build/runs \
		--run-id design-demo --report-only \
		--script benchmarks/protocol-v1/fixtures/plan-demo.json

baseline: ## run S0 (single prompt, no canon) for the same task
	$(RUN) scripts/run_pipeline.py --task t01 --system s0 --out build/runs \
		--script benchmarks/protocol-v1/fixtures/draft-baseline-demo.json --report-only

story-s2: ## run S2 end to end (S1 + revision) with the scripted fixture
	$(RUN) scripts/run_pipeline.py --task t01 --system s2 --out build/runs \
		--script benchmarks/protocol-v1/fixtures/pipeline-s2s3-demo.json --report-only

story-s3: ## run S3 end to end (S2 + voice pass) with the scripted fixture
	$(RUN) scripts/run_pipeline.py --task t01 --system s3 --out build/runs \
		--script benchmarks/protocol-v1/fixtures/pipeline-s2s3-demo.json --report-only

brief: ## check the premise-brief demo (good: 0 findings / bad: 6 failed checks)
	$(RUN) scripts/check_brief.py --brief harness/cases/brief-demo/brief.yaml
	-$(RUN) scripts/check_brief.py --brief harness/cases/brief-demo/brief-bad.yaml --fail-on none

world: ## check the world-rules demo against the demo canon
	$(RUN) scripts/check_world.py --world harness/cases/world-demo/world.yaml \
		--canon harness/cases/demo/canon

history: ## check the history-timeline demo against the demo canon
	$(RUN) scripts/check_history.py --history harness/cases/history-demo/history.yaml \
		--canon harness/cases/demo/canon

character: ## check the character-core demo against the demo canon
	$(RUN) scripts/check_character.py --characters harness/cases/character-demo/characters.yaml \
		--canon harness/cases/demo/canon

relation: ## check the relationship-web demo against the demo canon
	$(RUN) scripts/check_relation.py --relations harness/cases/relation-demo/relations.yaml \
		--canon harness/cases/demo/canon

plot: ## check the plot-architecture demo against the demo canon
	$(RUN) scripts/check_plot.py --plot harness/cases/plot-demo/plot.yaml \
		--canon harness/cases/demo/canon

scene: ## check the scene-information demo against the demo canon
	$(RUN) scripts/check_scene.py --scenes harness/cases/scene-demo/scenes.yaml \
		--canon harness/cases/demo/canon

branch: ## check the interactive-branch demo (self-contained)
	$(RUN) scripts/check_branch.py --branches harness/cases/branch-demo/branches.yaml

adaptation: ## check the adaptation demo (self-contained)
	$(RUN) scripts/check_adaptation.py --adaptation harness/cases/adaptation-demo/adaptation.yaml

voice: ## check the voice-style demo (4 seeded findings)
	-$(RUN) scripts/check_voice.py --voice harness/cases/voice-demo/voice.yaml \
		--text harness/cases/voice-demo/text --fail-on none

revise: ## run the revision-loop demo (critique -> patch -> re-audit -> compare)
	$(RUN) scripts/audit_continuity.py --canon harness/cases/revision-demo/canon \
		--text harness/cases/revision-demo/text --out build/revise/before.json \
		--fail-on none --quiet
	$(RUN) scripts/revise.py --mode plan --audit build/revise/before.json \
		--out build/revise/critique.json --quiet
	$(RUN) scripts/revise.py --mode apply --text harness/cases/revision-demo/text \
		--patch harness/cases/revision-demo/patch.json --out build/revise/text --quiet
	$(RUN) scripts/audit_continuity.py --canon harness/cases/revision-demo/canon \
		--text build/revise/text --out build/revise/after.json --fail-on none --quiet
	$(RUN) scripts/revise.py --mode compare --before build/revise/before.json \
		--after build/revise/after.json

calibrate: ## replay the frozen L2/L3 fixture demo (not a new calibration)
	$(RUN) scripts/calibrate_judge.py --labels harness/fixtures/labels-demo \
		--verdicts harness/fixtures/verdicts-demo.json

plan: ## run only the Plan step (task -> canon)
	$(RUN) scripts/run_pipeline.py --task t01 --stage plan --out build/runs \
		--script benchmarks/protocol-v1/fixtures/plan-demo.json

experiment: ## run the S0/S1 matrix with the scripted fixture (wiring only)
	$(RUN) scripts/run_experiment.py --id demo-scripted --tasks t01 \
		--systems s0 s1 --seeds 0 1 --out build/experiments/demo-scripted

# The six cells of experiments/2026-10-pilot-t01-s0s1, against a pinned model.
# Requires a key in the environment (never in the repository) and a fresh id:
#   make pilot-model MODEL=gpt-4.1 MODEL_VERSION=2025-04-14 EXPERIMENT=2026-10-gpt41-t01
MODEL           ?=
MODEL_VERSION   ?= unknown
BASE_URL        ?= https://api.openai.com/v1
EXPERIMENT      ?= 2026-10-model-t01-s0s1

# Blind A/B packets for L3 judging. Keep key.json away from the rater.
RUNS_ROOT       ?= runs
BASELINE        ?= s0
CANDIDATE       ?= s1
PAIRS_OUT       ?= build/pairs/latest

blind-pairs: ## frozen tooling: rebuild A/B packets from existing runs/ (no new L3 study)
	@test -d "$(RUNS_ROOT)" || { echo "error: no runs directory: $(RUNS_ROOT)"; exit 2; }
	$(RUN) scripts/make_blind_pairs.py --runs-root $(RUNS_ROOT) \
		--baseline $(BASELINE) --candidate $(CANDIDATE) --out $(PAIRS_OUT)

SYSTEMS       ?= s0 s1

pilot-model: ## run t01 x seed 0-2 x $(SYSTEMS) against a pinned model (needs MODEL + key)
	@test -n "$(MODEL)" || { echo "error: set MODEL, e.g. make pilot-model MODEL=gpt-4.1"; exit 2; }
	@test ! -e experiments/$(EXPERIMENT)/results.json || test -n "$(FORCE)" || \
		{ echo "error: experiments/$(EXPERIMENT)/results.json exists; pick a new id (or FORCE=1 to overwrite)"; exit 2; }
	$(RUN) scripts/run_experiment.py --id $(EXPERIMENT) --tasks t01 \
		--systems $(SYSTEMS) --seeds 0 1 2 --provider command \
		--command "$(RUN) scripts/model_adapter.py --model $(MODEL) --model-version $(MODEL_VERSION) --base-url $(BASE_URL)" \
		--model $(MODEL) --model-version $(MODEL_VERSION) \
		--out experiments/$(EXPERIMENT)

ci: ## run exactly what `research-check` runs (catalog, tests, demo artifacts)
	$(RUN) scripts/build_research_catalog.py --check
	$(RUN) -m pytest tests -q
	$(RUN) scripts/audit_continuity.py --canon harness/cases/demo/canon \
		--text harness/cases/demo/text --out build/ci/audit.json \
		--markdown build/ci/audit.md --fail-on none --quiet
	$(RUN) scripts/run_evaluation.py --candidate harness/cases/demo/text \
		--baseline harness/cases/demo-baseline/text --canon harness/cases/demo/canon \
		--rubric harness/rubrics/story-quality-v0.yaml --patterns harness/patterns.yaml \
		--judge-fixture harness/fixtures/judgements-demo.json --out build/ci/eval --report-only >/dev/null

gamelog-check: ## check the scripted Stage A game log against canon/plot/scenes
	$(RUN) scripts/check_gamelog.py \
		--game-log experiments/2026-10-trpg-slice-t01/inputs/game_log.json \
		--canon experiments/2026-10-trpg-slice-t01/inputs/canon \
		--design-dir experiments/2026-10-trpg-slice-t01/inputs/design \
		--require-design --fail-on high --quiet \
		--out build/twostage/game_log.json --markdown build/twostage/game_log.md

two-stage: ## run Stage A -> Stage B with the fixed scripted bundle
	$(RUN) scripts/run_twostage.py --task t01 \
		--canon experiments/2026-10-trpg-slice-t01/inputs/canon \
		--design-dir experiments/2026-10-trpg-slice-t01/inputs/design \
		--provider scripted \
		--script experiments/2026-10-trpg-slice-t01/scripted.json \
		--out experiments/2026-10-trpg-slice-t01/bundle \
		--results experiments/2026-10-trpg-slice-t01/results.json \
		--report-only --quiet

probe-gamelog: ## re-run the read-only contract probes on the t01 bundle (see the audit doc)
	$(RUN) scripts/probe_gamelog_contracts.py

protocol-check: ## verify the frozen evaluation protocol and its task set
	$(RUN) -m pytest tests/test_protocol.py -q

skills-check: ## validate SKILL.md files and run every skill's tests
	$(RUN) -m pytest tests/test_skills_spec.py tests/test_continuity.py \
		tests/test_evaluation.py tests/test_premise_brief.py tests/test_world_rules.py \
		tests/test_history_timeline.py tests/test_character_core.py \
		tests/test_relationship_web.py tests/test_plot_architecture.py \
		tests/test_scene_information.py tests/test_voice_style.py \
		tests/test_revision_loop.py tests/test_interactive_branch.py \
		tests/test_adaptation.py tests/test_pipeline_s2s3.py tests/test_pipeline_design.py \
		tests/test_calibration.py -q

clean: ## remove the generated texts and PDFs
	rm -rf data/raw data/pdf

distclean: clean ## also remove the download cache
	rm -rf data/cache
