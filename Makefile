# Makefile for xianmalik_cv
# Targets: build (default), watch, open, clean, deps, venv

# Auto-load .env if it exists and export its variables to subprocesses.
# Format: KEY=value (one per line, # for comments — no quotes, no 'export' prefix).
-include .env
export GROQ_API_KEY

.PHONY: build watch open clean deps venv lint format test release docker-build ats ats-deps

BUILD_SCRIPT := ./core/scripts/build.py
PDF := dist/resume.pdf
VENV_DIR := .venv
PY := $(VENV_DIR)/bin/python3
PIP := $(VENV_DIR)/bin/pip

build: deps
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) $(BUILD_SCRIPT)

deps: venv
	@$(PY) -c "import yaml" >/dev/null 2>&1 || $(PIP) install -r requirements.txt

venv:
	@command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }
	@[ -d $(VENV_DIR) ] || python3 -m venv $(VENV_DIR)
	@$(PIP) -q install --upgrade pip

watch: deps
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) ./core/scripts/watch.py

open: build
	@([ -f $(PDF) ] && open $(PDF)) || { echo "$(PDF) not found"; exit 1; }

clean:
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) ./core/scripts/clean.py

lint: deps
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) core/scripts/validate.py

format: deps
	@$(PIP) -q install black 2>/dev/null; \
	 PATH="$(VENV_DIR)/bin:$$PATH" $(VENV_DIR)/bin/black core/scripts/

test: deps
	@echo "Running YAML validation..."
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) core/scripts/validate.py
	@echo "Running generator smoke test..."
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) core/scripts/generate.py
	@echo "Running unit tests..."
	@$(PY) -c "import pytest" >/dev/null 2>&1 || $(PIP) install -q pytest
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) -m pytest tests/ -q
	@echo "All checks passed."

release: deps
	@[ -n "$(VERSION)" ] || { echo "Usage: make release VERSION=x.y.z"; exit 1; }
	@echo "$(VERSION)" > VERSION
	@git add VERSION
	@git commit -m "chore: release v$(VERSION)"
	@git tag "v$(VERSION)"
	@echo "Tagged v$(VERSION) — push with: git push && git push --tags"

docker-build:
	@docker build -t folia .
	@docker run --rm -v "$(PWD)/dist:/app/dist" folia

# Install spaCy and its model — only needed when running without an LLM API key.
ats-deps: deps
	@$(PY) -c "import spacy; spacy.load('en_core_web_sm')" >/dev/null 2>&1 || \
	 { printf "Installing spaCy prerequisites... "; \
	   $(PIP) install -r requirements-ats.txt >/dev/null 2>&1 && \
	   $(PY) -m spacy download en_core_web_sm >/dev/null 2>&1 && \
	   printf "✓\n"; }

# ── Smart unified ATS target ────────────────────────────────────────────────
#
#   make ats              → CV health check
#   make ats JD=jd.txt   → JD match  (JD or jd, either case works)
#
# Backend selection (automatic, no flags needed):
#   GROQ_API_KEY set in .env  →  LLM  (semantic matching, no extra installs)
#   GROQ_API_KEY not set      →  NLP  (run `make ats-deps` first)
#
# Override flags still work directly via Python if needed:
#   .venv/bin/python3 core/scripts/ats_check.py --jd jd.txt --no-llm
# ────────────────────────────────────────────────────────────────────────────

# Coalesce JD and jd into a single variable (whichever was passed).
_JD := $(or $(JD),$(jd))

ats: deps
	@$(PY) -c "import pypdf" >/dev/null 2>&1 || $(PIP) install -q -r requirements-ats.txt
	@if [ -n "$(_JD)" ]; then \
		PATH="$(VENV_DIR)/bin:$$PATH" $(PY) core/scripts/ats_check.py --jd "$(_JD)"; \
	else \
		PATH="$(VENV_DIR)/bin:$$PATH" $(PY) core/scripts/ats_check.py; \
	fi
