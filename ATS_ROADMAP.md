# ATS Modernization — Execution Roadmap

Sequenced, executable plan for upgrading `ats/` to score ≥90 on real-world JDs. Companion to the research plan at `arcanum/00-Inbox/ATS Checker — Modernization Research Plan.md`.

Each step is sized to land as its own PR. Steps within a milestone are ordered by dependency; do not skip ahead.

---

## Milestone 0 — Prerequisites (do these before any scoring change)

Without these, you cannot measure whether subsequent changes actually help.

### 0.1 Build a JD sample corpus
- **Goal:** 5 representative real-world JDs as fixtures.
- **Files:** new `samples/jds/{staff-fullstack,senior-backend,frontend-react,devops-aws,data-eng}.txt`
- **Source:** copy-paste from real postings (LinkedIn, Wellfound, Greenhouse-hosted).
- **Verify:** `ls samples/jds/*.txt | wc -l` == 5.

### 0.2 Add a pytest harness
- **Goal:** first automated tests for ATS — currently zero coverage.
- **Files:** new `tests/test_ats_jd_matcher.py`, `tests/test_ats_health.py`, `tests/conftest.py` (fixture loading a frozen `ResumeData`), `pytest.ini`. Add `pytest>=8.0` to `requirements.txt`.
- **Tests to write first:**
  - `test_load_resume_data_smoke()` — loader returns non-empty `ResumeData`
  - `test_jd_matcher_returns_known_shape()` — run against `samples/jds/senior-backend.txt`, assert all four sub-scores in [0, 100]
  - `test_health_passes_on_current_resume()` — current resume should already pass health threshold
- **Files:** add `make test-ats` target to Makefile.
- **Verify:** `make test-ats` — three green dots.

### 0.3 Capture baseline scores
- **Goal:** numbers we can compare against.
- **Action:** run `make ats-jd JD=samples/jds/<each>.txt` and record overall + sub-scores in a new `samples/jds/_baseline.md`.
- **Verify:** `_baseline.md` table has 5 rows × 6 columns (jd, overall, kw, title, exp, edu).

---

## Milestone 1 — pdflatex Migration

Highest single-change ATS impact. Eliminates the #1 PDF-extraction failure mode. **Order matters here — do not start step 1.3 until 1.2 builds clean.**

### 1.1 Font compatibility audit
- **Goal:** know exactly what `xianmalik.cls` does that pdflatex can't handle.
- **Action:** grep for `\RequirePackage{fontspec}`, `\setmainfont`, `\fontspec`, `\newfontfamily` across `xianmalik.cls` and `core/*.tex`. Inventory all custom font commands.
- **Known blockers (from initial read):**
  - `core/fonts.tex` lines 2–11: `fontspec` + `\setmainfont` loading Inter Variable TTF
  - `core/fonts.tex` lines 14–18: five `\fontspec{Inter}[...]` font commands
- **Verify:** write findings to a `pdflatex-migration-audit.md` (delete after migration completes).

### 1.2 Replace fontspec with pdflatex-compatible font
- **Goal:** keep Inter (or visually similar) under pdflatex.
- **Options (pick one):**
  - **A — Inter via package:** install `inter` LaTeX package, `\usepackage[default]{inter}` + `\usepackage[T1]{fontenc}`. Closest visual match.
  - **B — Latin Modern Sans:** `\usepackage{lmodern}` + `\renewcommand{\familydefault}{\sfdefault}`. Zero extra deps, broadly available.
  - **C — Open Sans:** `\usepackage[default]{opensans}`. Common, ATS-friendly.
- **Files:** rewrite `core/fonts.tex`; remove `font/Inter-Variable.ttf` if option A or C chosen (keep if B and you still want the file).
- **Verify:** PDF still compiles via a one-off `pdflatex -output-directory=dist resume.tex` outside the build script.

### 1.3 Switch build pipeline to pdflatex
- **Files:**
  - `scripts/build.py` lines 162–172 — change `"xelatex"` → `"pdflatex"`, update banner string at line 43.
  - `.github/workflows/release.yml` — TeX Live install may need adjustment; `pdflatex` is in the base distribution.
  - `Makefile` — no change expected; uses `build.py`.
- **Verify:** `make build` produces `dist/resume.pdf` and `dist/resume-v<version>.pdf` with identical visual layout to the XeLaTeX output.

### 1.4 PDF text-extraction validator
- **Goal:** programmatic proof the PDF is ATS-extractable.
- **Files:** new `ats/pdf_validator.py`. Use `pdfminer.six` (pure Python, no system binary). Add `pdfminer.six>=20231228` to `requirements.txt`.
- **API:** `validate_pdf(pdf_path) -> PDFValidationResult` with fields `text`, `word_count`, `has_garbled_chars`, `coherent_top_down`, `warnings: list[str]`.
- **Checks:**
  - Word count ≥150 (reasonable resume length)
  - No replacement glyphs (`�`) or stray control characters
  - First non-empty line contains the user's name (read from `resume.tex` contact macros)
  - "experience" or "education" string appears in extracted text
- **Files:** new CLI flag `--validate-pdf` on `scripts/ats_check.py`; new Makefile target `ats-pdf-check`.
- **Verify:** `make ats-pdf-check` returns exit 0 on a freshly-built PDF.

---

## Milestone 2 — Phase 1 Scoring Improvements (no AI)

Order does not strictly matter inside this milestone — but ship them as separate small PRs.

### 2.1 Must-have vs preferred keyword extraction
- **Goal:** distinguish knockout keywords from bonuses.
- **Files:**
  - `ats/data/keywords.json` — add `must_have_section_patterns: ["requirements", "qualifications", "must.?have", "required", "essential", "you have", "you bring"]` and `preferred_section_patterns: ["preferred", "nice.?to.?have", "bonus", "plus", "good to have"]`.
  - `ats/jd_matcher.py` — split JD text into `{must, preferred, neutral}` chunks before calling `_extract_jd_keywords`. Tag each emitted keyword with `tier: "must" | "preferred" | "neutral"` on the `KeywordMatch` dataclass.
  - `ats/config.yml` — new `jd_match.tier_multipliers: { must: 2.0, preferred: 1.0, neutral: 0.75 }`.
- **Scoring change:** `keyword_score` becomes a weighted average where each matched keyword contributes `score × tier_multiplier`. Missing `must` tier keywords subtract a fixed penalty (configurable, default 5 pts per miss, cap at -30).
- **Verify:** new test `test_jd_matcher_penalizes_missing_musthave()` — synthesize a JD with a fake "must have: Kotlin" line on a Kotlin-less resume, assert overall drops ≥15 pts vs same JD without that line.

### 2.2 Frequency-weighted scoring
- **Goal:** terms repeated in the JD count more.
- **Files:** `ats/jd_matcher.py` `_extract_jd_keywords` — return `list[tuple[str, int]]` (keyword, JD frequency) instead of plain `list[str]`.
- **Scoring change:** in the keyword-loop in `run()` (lines 396–404), multiply `score` by `log1p(jd_frequency)`. Normalize so a JD with a single 1×-frequency keyword still gets full credit.
- **Verify:** new test — duplicate a keyword 5× in a JD, assert keyword's contribution rises but does not dominate (log scaling).

### 2.3 Section-aware match scoring
- **Goal:** matching in "Skills" should beat matching in "Experience" body.
- **Files:** `ats/jd_matcher.py` `_score_keyword` (lines 228–254) — when iterating `section_texts`, weight each section's contribution: `skills=1.0, experience=0.85, projects=0.85, summary=0.70, education=0.50`. Move these multipliers into `ats/config.yml` under `jd_match.section_weights`.
- **Verify:** new test — same keyword present only in skills vs only in summary; skills-only run scores higher.

### 2.4 Ontology expansion via ESCO subset
- **Goal:** ~10× more skill mappings without manual curation.
- **Action:** download ESCO v1.2.0 JSON release; write a one-off `scripts/build_ontology.py` that filters to ICT-relevant skill clusters (info-tech, software, data, cloud) and merges into the existing `implies`/`aliases` shape.
- **Files:**
  - new `scripts/build_ontology.py`
  - regenerated `ats/data/ontology.json` (commit the merged result, not the raw ESCO dump)
- **Constraints:** keep `ontology.json` ≤ 500KB. Prefer ~2–3k canonical skills with 1–3 implications each.
- **Verify:** existing tests still pass; new test `test_ontology_recognizes_common_aliases()` checks `node`, `js`, `k8s`, `postgres`, `tf` (terraform) resolve correctly.

### 2.5 Integrity check (anti-stuffing, anti-hidden-text)
- **Goal:** catch and penalize keyword stuffing or invisible text in the source.
- **Files:** new `ats/integrity.py`. API: `check_integrity(resume: ResumeData, pdf_path: Path | None) -> IntegrityResult`.
- **Checks:**
  - **Keyword density:** for each unique skill mentioned in `ResumeData.all_text()`, compute occurrences / 100 words. Flag any token appearing > 5× per 100 words.
  - **Hidden text (PDF mode only):** parse PDF via `pdfminer.six`, extract text fragments with their color. Flag any fragment where text color ≈ background color (Δ < 30 in RGB).
  - **Repetition pattern:** detect lists of comma-separated skills > 50 items in a row (stuffing tell).
- **Scoring:** each flag deducts a fixed penalty from the overall score (configurable, default -10 per flag).
- **Wire-up:** call from `scripts/ats_check.py`; show as a "Integrity" section in renderer output.
- **Verify:** synthesize a stuffed resume (200 random keywords appended to summary), assert integrity flag fires and overall drops ≥10.

### 2.6 Renderer: surface must-have gaps prominently
- **Files:** `ats/renderer.py` — add a dedicated "Critical gaps" block at the top of JD report when any `must`-tier keywords are missing. Use red/bold ANSI. Currently missing keywords are shown in a flat list — change to grouped (`Must-have missing`, `Preferred missing`, `Other missing`).
- **Verify:** visual check on a JD with deliberate must-have gaps.

### 2.7 Re-baseline
- **Action:** re-run the 5 sample JDs, update `samples/jds/_baseline.md` with `before` and `after_phase_1` columns.
- **Target:** median +10 to +15 pts.

---

## Milestone 3 — Phase 2 Semantic Layer

Local AI only. No API keys, no costs.

### 3.1 Add embeddings dependencies
- **Files:** `requirements.txt` — add `sentence-transformers>=2.7` and `numpy>=1.26`. (sentence-transformers brings in torch as a transitive dep — ~500MB install, acceptable.)
- **Makefile:** new `ats-deps-semantic` target that downloads the model once on first run.

### 3.2 Build `ats/embeddings.py`
- **API:**
  ```python
  def encode(texts: list[str]) -> np.ndarray         # returns (N, 384)
  def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray
  def get_model() -> SentenceTransformer              # lazy-load, cache in module
  ```
- **Cache:** model auto-cached in `~/.cache/huggingface/`. Add `~/.cache/folia/` for any folia-specific intermediate caches.
- **Lazy load:** do not import `sentence_transformers` at module top — only inside `get_model()`. Health mode must still work without it.

### 3.3 Semantic score band in `_score_keyword`
- **Files:** `ats/jd_matcher.py` lines 228–254.
- **Logic:** after fuzzy match fails, run semantic check — encode the JD keyword once, encode each skill item once (cache per run), find max cosine. Score band: `0.55` for cosine ≥ 0.65, `0.0` otherwise. Move both threshold and score into `ats/config.yml`.
- **Verify:** new test — JD says "API design", resume says "REST endpoint engineering" — semantic match scores 0.55.

### 3.4 Bullet-vs-requirement matrix
- **Goal:** show the user which JD line is supported by which resume bullet, surface the un-backed ones.
- **Files:**
  - `ats/jd_matcher.py` — new method on `JDResult`: `bullet_evidence: dict[str, list[tuple[str, float]]]` mapping each requirement-line to top-3 (bullet, cosine) tuples.
  - `ats/renderer.py` — new "Coverage Matrix" section, shows requirements with no bullet ≥ 0.5 cosine in red.
- **Verify:** visual check; should highlight obvious gaps.

### 3.5 Re-baseline
- Update `_baseline.md` with `after_phase_2` column. Target median +5 to +8 pts on top of Phase 1.

---

## Milestone 4 — Phase 3 LLM Augmentation (opt-in)

Cloud-LLM features. Silent no-op when no API key is set.

### 4.1 Build `ats/llm.py`
- **Files:** new `ats/llm.py`. Add `anthropic>=0.40` and `openai>=1.50` to `requirements.txt` (both lazy-imported).
- **API:**
  ```python
  def is_available() -> bool                                       # any API key present?
  def parse_jd(jd_text: str) -> dict                              # {must_have, nice_to_have, responsibilities, screening}
  def grade_bullet(bullet: str, jd_context: str) -> dict          # {score, star_format, quantified, action_strength, jd_relevance, suggestion}
  def gap_analysis(resume_summary: str, jd: str, missing: list[str]) -> str
  ```
- **Provider gating:** prefer `ANTHROPIC_API_KEY` (use claude-haiku-4-5 for cost), fall back to `OPENAI_API_KEY` (use gpt-4o-mini). Skip if neither set.
- **Cost guardrail:** count tokens before sending; if `len(jd_text.split()) > 3000` and `--llm-force` not passed, refuse and tell the user.

### 4.2 Wire structured JD parser into scoring
- **Goal:** use LLM's must/nice-to-have extraction in place of regex section detection (Phase 1 step 2.1) when LLM is available.
- **Files:** `ats/jd_matcher.py` — in `run()`, if `llm.is_available()` and `--llm` flag passed, call `llm.parse_jd()` and use its `must_have` / `nice_to_have` lists as canonical tier assignments. Regex tagging remains the fallback.
- **Verify:** test with both `ANTHROPIC_API_KEY` set and unset; behaviour differs gracefully.

### 4.3 Bullet quality grading
- **Files:** `ats/llm.py` `grade_bullet()` + new section in `ats/renderer.py` output.
- **Caching:** cache per-bullet results keyed by `sha256(bullet + jd_title)` in `~/.cache/folia/bullet_grades.json` to avoid re-billing across runs.

### 4.4 Gap analysis prose
- **Files:** `ats/llm.py` `gap_analysis()` + final block in renderer when `--llm` is set.

### 4.5 CLI plumbing
- **Files:** `scripts/ats_check.py` — add `--llm` flag (off by default even when key set), `--llm-force` (bypass token cap), `--llm-provider {anthropic,openai}`. Update `Makefile` with `make ats-llm JD=...`.

### 4.6 Final validation
- **Action:** with `--llm` enabled, run the 5-JD baseline. Document final scores in `_baseline.md` with `after_phase_3` column.
- **Acceptance:** at least one JD ≥ 90; median across the 5 ≥ 85.

---

## Cross-cutting concerns

- **No scope creep mid-PR.** Each numbered step is its own commit/PR. Don't fold 2.2 into 2.1 just because they touch the same file.
- **Tests gate everything from 0.2 onward.** Any PR that doesn't add or update a test fails review.
- **`config.yml` is the single source of truth** for all thresholds. Never hard-code a number in a scoring function — always read it from config.
- **Renderer changes go last in each milestone.** Get the data right before deciding how to display it.
- **Keep PR diffs reviewable.** If a step blows past ~300 lines diff, split it.

---

## Quick execution checklist

- [x] 0.1 — JD samples (`samples/jds/*.txt`)
- [x] 0.2 — pytest harness (`tests/`, 19 tests green)
- [x] 0.3 — baseline capture (`samples/jds/_baseline.md`)
- [x] 1.1 — font audit (fontspec → lmodern)
- [x] 1.2 — fontspec replacement (`core/fonts.tex`)
- [x] 1.3 — pdflatex switch (`scripts/build.py`, GitHub Actions)
- [x] 1.4 — PDF extraction validator (`ats/pdf_validator.py`, `--validate-pdf`)
- [x] 2.1 — must-have / preferred tiers (`_tier_jd_sections`, tier multipliers in config)
- [x] 2.2 — frequency weighting (`log1p(freq)` in scoring loop)
- [x] 2.3 — section-aware scoring (`_SECTION_WEIGHTS`, skills>exp>summary>edu)
- [x] 2.4 — Ontology v2.0 expansion (~30 new entries, ~60 new aliases)
- [x] 2.5 — integrity check (`ats/integrity.py` — density, hidden-text, repetition)
- [x] 2.6 — renderer must-have gaps (prominent red block, tier badges)
- [x] 2.7 — Phase 1 re-baseline (**median 62.4 → 76.6**, 0/5 → 4/5 passing)
- [x] 3.1 — embeddings deps (optional, CPU-only torch required in WSL)
- [x] 3.2 — `ats/embeddings.py` (bulk_semantic_scores, graceful no-op without ST)
- [x] 3.3 — semantic score band (`use_semantic` flag, `--semantic` CLI, `--no-semantic`)
- [ ] 3.4 — coverage matrix (bullet-vs-requirement display in renderer)
- [ ] 3.5 — Phase 2 re-baseline (requires sentence-transformers installed)
- [x] 4.1 — `ats/llm.py` (parse_jd, grade_bullets, gap_analysis, anthropic+openai)
- [x] 4.2 — LLM JD parser wiring (`run(..., use_semantic=...)`, llm flag)
- [x] 4.3 — bullet grading (`grade_bullets()` in `ats/llm.py`)
- [x] 4.4 — gap analysis (`gap_analysis()` in `ats/llm.py`)
- [x] 4.5 — CLI plumbing (`--llm`, `--semantic`, `--no-semantic`, `make ats-llm`, `make ats-semantic`)
- [ ] 4.6 — final validation (run with LLM enabled once API key set)
