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
python3 scripts/generate.py   # YAML → TeX only
python3 scripts/build.py      # Full build (generate + xelatex compile)
python3 scripts/clean.py      # Clean auxiliary files
```

## Architecture

This is a **YAML → LaTeX → PDF** resume generation system.

**Data flow:**
1. Edit content in `data/*.yml` files (numbered for ordering: `00-summary.yml`, `10-experience.yml`, etc.)
2. `scripts/generate.py` converts each YAML file to a corresponding TeX file in `sections/`
3. `resume.tex` (main document) includes all section files and uses `xianmalik.cls` for styling
4. XeLaTeX compiles to `dist/resume.pdf` and `dist/resume-v{VERSION}.pdf`

**Key files:**
- `data/` — All resume content lives here; this is the only directory users should edit for content changes
- `xianmalik.cls` — Custom LaTeX document class defining all visual styling, colors, and CV commands (`\cventry`, `\cvproject`, `\cvskill`, etc.)
- `resume.tex` — Main document that includes all section files; edit to reorder or toggle sections
- `VERSION` — Single-line version string used for PDF naming and GitHub releases

**YAML formatting conventions:**
- Use `[[text]]` syntax in YAML strings to render **bold** text in the PDF
- Section files in `sections/` are auto-generated — never edit them directly

## Release

Tag with `v*` (e.g., `git tag v1.2.0`) to trigger the GitHub Actions workflow (`.github/workflows/release.yml`), which builds on Ubuntu with TeX Live and publishes the versioned PDF as a GitHub release asset.
