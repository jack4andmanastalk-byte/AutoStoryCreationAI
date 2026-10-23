PYTHON ?= python3
VENV    ?= .venv
BIN     := $(VENV)/bin
CONFIG  ?= configs/dataset.yaml
WORK    ?= 120

.PHONY: help setup test data data-aozora data-narou pull-datasets report research research-check clean distclean

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

data-narou: ## Syosetsuka ni Narou: bibliographic records, texts and PDFs
	$(BIN)/python scripts/fetch_narou_api.py --config $(CONFIG)
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-metadata
	$(BIN)/python scripts/setup_dataset.py --config $(CONFIG) narou-texts --works 20 --pdf --check-commercialization

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

clean: ## remove the generated texts and PDFs
	rm -rf data/raw data/pdf

distclean: clean ## also remove the download cache
	rm -rf data/cache
