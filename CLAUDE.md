# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make deps        # Create .venv and install Python dependencies (PyYAML)
make build       # Generate TeX from YAML and compile to dist/resume.pdf
make watch       # Auto-rebuild on file changes (requires fswatch: brew install fswatch)
make open        # Build and open PDF in default viewer
make clean       # Remove LaTeX auxiliary files from dist/
```

Direct Python equivalents:
```bash
python3 core/scripts/generate.py   # YAML → TeX only
python3 core/scripts/build.py      # Full build (generate + xelatex compile)
python3 core/scripts/clean.py      # Clean auxiliary files
```

## Repository layout

- `source/` — All resume content (the YAML data files); this is the only directory users edit for content changes
- `core/` — Everything needed to build the CV:
  - `core/scripts/` — `generate.py`, `build.py`, `clean.py`, `validate.py`, `watch.py`, `ats_check.py`
  - `core/sections/` — auto-generated TeX sections (never edit directly)
  - `core/partials/` — modular LaTeX class partials (`colors.tex`, `fonts.tex`, `layout.tex`, `styles.tex`, `commands.tex`, `structure.tex`)
  - `core/font/` — bundled fonts (Inter, Font Awesome)
  - `core/resume.tex` — main LaTeX document
  - `core/xianmalik.cls` — custom CV document class (loads `core/partials/`)
- `ats/` — ATS health-check and JD-matching package
- `docs/` — supplementary documentation (`CUSTOMIZATION.md`, `TODO.md`)
- `dist/` — built PDF output
- `VERSION` — single-line version string used for PDF naming and GitHub releases

## Architecture

This is a **YAML → LaTeX → PDF** resume generation system.

**Data flow:**
1. Edit content in `source/*.yml` files (numbered for ordering: `00-summary.yml`, `10-experience.yml`, etc.)
2. `core/scripts/generate.py` converts each YAML file to a corresponding TeX file in `core/sections/`
3. `core/resume.tex` (main document) includes all section files and uses `core/xianmalik.cls` for styling
4. XeLaTeX is run with `core/` as the working directory and compiles to `dist/resume.pdf` and `dist/resume-v{VERSION}.pdf`

**YAML formatting conventions:**
- Use `[[text]]` syntax in YAML strings to render **bold** text in the PDF
- Section files in `core/sections/` are auto-generated — never edit them directly

## Release

Tag with `v*` (e.g., `git tag v1.2.0`) to trigger the GitHub Actions workflow (`.github/workflows/release.yml`), which builds on Ubuntu with TeX Live and publishes the versioned PDF as a GitHub release asset.
