# Folia — TODO

## High Impact

- [x] Fix silent failures in `generate.py` — `read_yaml()` swallows exceptions silently; skipped sections produce no warning
- [x] Fix fragile escaping in `latex_escape()` — magic placeholder strings (`BOLDSTART9E8F7A`) break if user data contains them; replace with regex split
- [x] Deduplicate entry generation — `gen_experience()`, `gen_education()`, `gen_projects()` repeat the same cvitems loop; extract a shared helper
- [x] Remove unused `compile_xelatex()` in `build.py` — defined at line 130 but never called; logic is duplicated inline
- [x] Strengthen `validate.py` — projects only requires `name` but generator expects `subtitle`, `items`, `tech`, `url` too; nested fields go unchecked
- [x] Improve XeLaTeX error output — only shows first 5 `!` lines with no context; show ±3 surrounding lines per error

## Medium Impact

- [x] Fix section file numbering mismatch — `data/` numbering doesn't match `sections/` or display order in `resume.tex`
- [x] Add type hints throughout `generate.py` — functions return `dict | None` without annotation; IDE support broken
- [x] Add docstrings to core generator functions
- [x] Deduplicate GitHub Actions setup steps — `build.yml` and `release.yml` repeat the full TeX Live + Python install sequence

## Polish / Dev Experience

- [ ] Add `argparse` CLI to scripts — `python3 scripts/build.py --help` currently does nothing
- [ ] Add `make test`, `make format`, `make lint` targets to Makefile
- [ ] Watch mode: visually distinguish failed vs successful builds
- [ ] Document Docker usage in README
- [ ] Add pre-commit hooks (black, flake8, YAML validation)
- [ ] Create `CUSTOMIZATION.md` — how to change colors, fonts, margins
