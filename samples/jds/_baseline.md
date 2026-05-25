# ATS Score Baseline

Captured before any modernization changes. Run via `make ats-jd JD=samples/jds/<name>.txt`.

## Scores — Before (v1 baseline)

| JD | Overall | Keyword | Title | Exp | Edu | KW extracted | KW matched |
|---|---|---|---|---|---|---|---|
| staff-fullstack | 64.8 | 47.4 | 43.3 | 100.0 | 100.0 | 62 | 30 |
| senior-backend | 62.4 | 46.6 | 35.0 | 100.0 | 100.0 | 53 | 25 |
| frontend-react | 69.2 | 37.5 | 76.7 | 100.0 | 100.0 | 73 | 28 |
| devops-cloud | 51.3 | 25.2 | 25.0 | 100.0 | 100.0 | 64 | 17 |
| ai-fullstack | 60.6 | 48.5 | 25.0 | 100.0 | 100.0 | 65 | 33 |
| **Median** | **62.4** | **46.6** | **35.0** | **100.0** | **100.0** | | |
| **Pass** | **0 / 5** | | | | | | |

## Scores — After Phase 1 / M2 (v2 — tier, frequency, section weights)

Changes applied:
- **pdflatex migration** (M1): XeLaTeX → pdflatex for ATS-safe text extraction
- **Ontology v2.0**: 30+ new implies entries, 60+ new aliases
- **Tier classification**: must-have vs. preferred vs. neutral sections
- **Frequency weighting**: `log1p(freq)` — high-frequency JD terms weighted more
- **Section-aware matching**: Skills(1.0) > Experience(0.85) > Summary(0.70) > Education(0.50)
- **Must-have penalty**: −5 pts per missed must-have keyword, capped at −30
- **Title normalization**: role synonyms (fullstack/frontend/backend → engineer), tech suffix strip
- **Keyword extraction fixes**: NOUN tokens restricted to known-tech; generic tech-adjacent nouns blocked

| JD | Overall | Keyword | Title | Exp | Edu | KW extracted | KW matched | Must-miss | Pass |
|---|---|---|---|---|---|---|---|---|---|
| staff-fullstack | 87.3 | 68.2 | 100.0 | 100.0 | 100.0 | 55 | 30 | 0 | ✓ |
| senior-backend | 76.6 | 41.5 | 100.0 | 100.0 | 100.0 | 51 | 22 | 3 | ✓ |
| frontend-react | 77.3 | 43.1 | 100.0 | 100.0 | 100.0 | 61 | 23 | 2 | ✓ |
| devops-cloud | 48.3 | 12.5 | 33.3 | 100.0 | 100.0 | 60 | 21 | 14 | ✗ |
| ai-fullstack | 70.3 | 56.9 | 50.0 | 100.0 | 100.0 | 59 | 29 | 2 | ✓ |
| **Median** | **76.6** | **43.1** | **100.0** | **100.0** | **100.0** | | | | |
| **Pass** | **4 / 5** | | | | | | | | |

**Delta from baseline:** +14.2 pts median, 4 additional JDs passing.

## Observations

### Phase 1 wins
- **Title match dramatically improved** (35 → 100 median): role-equiv normalization (fullstack/frontend/backend → "engineer") + title suffix stripping ("Senior Frontend Engineer — React" strips "— React") means all engineering JDs match correctly.
- **Staff-fullstack: +22.5 pts** (64.8 → 87.3) — this is the best-fit JD and now scores strongly.
- **Frontend-react: +8.1 pts** (69.2 → 77.3) — correctly passes now despite keyword gaps.
- **AI-fullstack: +9.7 pts** (60.6 → 70.3) — LLM/API skill matches improved via ontology expansion.

### Remaining gaps
- **DevOps JD still fails (48.3)**: 14 missing must-have keywords (Kubernetes, Terraform, Helm, AWS CDK…). This is a genuine skills gap — the resume is a Full-Stack engineer resume, not a DevOps resume. DevOps would only pass if those skills were added.
- **Keyword scores are still below 70** on all JDs. Phase 2 (semantic embedding layer) will close this by catching paraphrases that direct/fuzzy matching misses.
- **AI-fullstack title at 50**: JD title "AI-Integrated Full-Stack Engineer" — the "AI-Integrated" prefix doesn't map to any role equiv. Phase 2 may help via semantic title similarity.

### Targets

| Phase | Expected median | Passes |
|---|---|---|
| Baseline | 62.4 | 0 / 5 |
| After Phase 1 (✓ done) | ~75–80 | 3–4 / 5 |
| After Phase 2 (semantic embeddings) | ~83–88 | 4–5 / 5 |
| After Phase 3 (LLM opt-in) | ~88–92 | 4–5 / 5 |
| Goal | ≥90 on 3+ of 5 JDs | |

**Actual Phase 1 result: median 76.6, 4/5 passing — on target.**
