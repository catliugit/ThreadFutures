PY ?= python
export PYTHONPATH := src
export MPLBACKEND := Agg
export MLFLOW_DISABLE_AGENT_HINT := 1

.PHONY: all offcuts stock retail dbt stall experiment monitor regsearch test api site clean

all: offcuts stock test site

## Part 1: offcut forecasting (simulated cutting runs)
offcuts:
	$(PY) -m offcut.pipeline
	$(PY) -m offcut.train

## Part 2: unsold-stock analytics (real open retail data)
stock: retail dbt stall experiment monitor regsearch

retail:        ## download UCI Online Retail II and land it as Parquet (bronze)
	$(PY) -m stock.ingest

dbt:           ## silver + gold models and 28 data tests
	cd dbt && DBT_PROFILES_DIR=. dbt build

stall:         ## train the stall-risk model, tracked in MLflow
	$(PY) -m stock.train_stall

experiment:    ## markdown difference-in-differences + routing pilot power analysis
	$(PY) -m stock.experiment

monitor:       ## accuracy and drift report -> site/reports/monitoring.html
	$(PY) -m stock.monitor

regsearch:     ## retrieval evaluation over the EU regulation text
	$(PY) -m regsearch.search

test:
	$(PY) -m pytest -q tests

api:           ## http://127.0.0.1:8000/docs
	uvicorn api.main:app --app-dir src --reload

site:          ## copy the browser model into the website
	$(PY) -c "import pathlib; m=pathlib.Path('models/pre_marker_model.json').read_text(); pathlib.Path('site/model.js').write_text('window.OFFCUT_MODEL=' + m + ';\n')"

mlflow-ui:
	mlflow ui --backend-store-uri sqlite:///data/mlflow.db

clean:
	rm -rf data/raw data/staged data/features data/*.duckdb dbt/target
