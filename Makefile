PYTHON ?= python3
VENV    ?= .venv
BIN     := $(VENV)/bin
CONFIG  ?= configs/dataset.yaml
WORK    ?= 120
# skills/harness need PyYAML: prefer the virtualenv when it exists
RUN     := $(shell [ -x $(BIN)/python ] && echo $(BIN)/python || echo $(PYTHON))

.PHONY: help setup test data data-aozora data-narou pull-datasets report research research-check audit evaluate plan story baseline skills-check protocol-check clean distclean

help: ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## create the virtual environment and install the dependencies
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

test: ## run the unit tests
	$(BIN)/python -m pytest tests -q

data: data-aozora data-narou ## download every dataset (metadata + texts + PDFs)

data-aozora: ## Aozora Bunko: bibliographic records, texts and PDFs
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) aozora-metadata
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) aozora-texts --works $(WORK) --pdf

data-narou: ## Syosetsuka ni Narou: bibliographic records, ranking, full-episode texts and PDFs
	$(BIN)/python scripts/fetch_narou_api.py --config $(CONFIG) --per-query 500 --order-pages 2
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-metadata --cached-only
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-rank --top 100
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-texts --works 100 --max-episodes 0 --pdf --rank-order

pull-datasets: ## fetch prebuilt datasets and PDFs from the 'datasets' branch
	git fetch origin +refs/heads/datasets:refs/remotes/origin/datasets
	mkdir -p data
	git archive origin/datasets | tar -x -C data

report: ## print statistics about the generated datasets
	$(BIN)/python scripts/dataset_report.py --config $(CONFIG)

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

story: ## run S1 end to end (plan -> draft -> audit) with the scripted fixture
	$(RUN) scripts/run_pipeline.py --task t01 --out build/runs \
		--script benchmarks/protocol-v1/fixtures/plan-demo.json --report-only

baseline: ## run S0 (single prompt, no canon) for the same task
	$(RUN) scripts/run_pipeline.py --task t01 --system s0 --out build/runs \
		--script benchmarks/protocol-v1/fixtures/draft-baseline-demo.json --report-only

plan: ## run only the Plan step (task -> canon)
	$(RUN) scripts/run_pipeline.py --task t01 --stage plan --out build/runs \
		--script benchmarks/protocol-v1/fixtures/plan-demo.json

protocol-check: ## verify the frozen evaluation protocol and its task set
	$(RUN) -m pytest tests/test_protocol.py -q

skills-check: ## validate SKILL.md files, run the demo audit and the evaluation tests
	$(RUN) -m pytest tests/test_skills_spec.py tests/test_continuity.py tests/test_evaluation.py -q

clean: ## remove the generated texts and PDFs
	rm -rf data/raw data/pdf

distclean: clean ## also remove the download cache
	rm -rf data/cache
