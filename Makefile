# Makefile for xianmalik_cv
# Targets: build (default), watch, open, clean, deps, venv

.PHONY: build watch open clean deps venv lint release docker-build

BUILD_SCRIPT := ./scripts/build.py
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
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) ./scripts/watch.py

open: build
	@([ -f $(PDF) ] && open $(PDF)) || { echo "$(PDF) not found"; exit 1; }

clean:
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) ./scripts/clean.py

lint: deps
	@PATH="$(VENV_DIR)/bin:$$PATH" $(PY) scripts/validate.py

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

