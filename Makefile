# Orchestration. On Windows without GNU make, `python make.py <target>` runs the same steps.
ifeq ($(OS),Windows_NT)
PY ?= .venv/Scripts/python
else
PY ?= .venv/bin/python
endif
export PYTHONUTF8 = 1
RUN = cd src && ../$(PY)

.PHONY: setup feasibility simulate ingest clean funnel power experiment guardrails segments \
        validation-sims decision claims validate export-web readme all test web lint

setup:
	python -m venv .venv && $(PY) -m pip install -r requirements.txt
feasibility:     ; $(RUN) feasibility.py
simulate:        ; $(RUN) simulate.py
ingest:          ; $(RUN) ingest.py
clean:           ; $(RUN) clean.py
funnel:          ; $(RUN) funnel.py
power:           ; $(RUN) power.py
experiment:      ; $(RUN) experiment.py
guardrails:      ; $(RUN) guardrails.py
segments:        ; $(RUN) segments.py
validation-sims: ; $(RUN) validation_sims.py
decision:        ; $(RUN) decision.py
claims:          ; $(RUN) claims.py
validate:        ; $(RUN) validate.py
export-web:      ; $(RUN) export_web.py
readme:          ; $(RUN) readme.py

all: simulate ingest clean funnel power experiment guardrails segments validation-sims decision claims validate export-web readme

test:
	$(PY) -m pytest -q
web:
	cd web && npm ci && npm run lint && npm run typecheck && npm test && npm run build
lint:
	$(PY) -m ruff check src tests
