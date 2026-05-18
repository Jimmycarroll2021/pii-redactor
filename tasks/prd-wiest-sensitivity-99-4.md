# PRD: Wiest-Grounded 99.4% Sensitivity for pii-redactor

## 1. Introduction / Overview

The pii-redactor README claims grounding in Wiest et al. (NEJM AI 2024, "LLM-Anonymizer"): **98.2% accuracy / 99.4% sensitivity** on medical PII using Llama-3-8B-Instruct + llama.cpp GBNF grammar.

Measured reality (2026-05-17, 100-doc Gretel sample, Ollama qwen2.5:7b on CPU): **97.89% sensitivity** — 1.51pp short. This PRD closes that gap so the claim becomes defensible and the project ships as a credible Wiest-grounded de-identifier.

The work also fixes 2 live unit-test regressions (phone-vs-ABN regex over-match) along the way to keep the codebase green.

## 2. Goals

- Achieve **≥99.4% sensitivity** on the 100-doc Gretel fixture using Llama-3.1-8B
- Achieve **≥99.4% sensitivity** on a 50-doc synthetic medical fixture (apples-to-apples Wiest comparison)
- Restore the unit test suite to **58/58 green** (currently 56/58; fix the 2 phone-regex regressions)
- Land **reproducible bench artifacts** in `scale-tests/runs/` plus a `.planning/PASS-GATE.md` so next session can verify the claim
- Update `README.md` to replace the unverified "98.2% / 99.4%" copy-paste with **actually-measured numbers** from this work

## 3. User Stories

### US-001: Restore unit test suite to all-green
**Description:** As a developer, I need 58/58 tests passing so CI is green before benching, and so the phone-regex false-positive on ABN-like spacing is removed from production.

**Acceptance Criteria:**
- [ ] `test_pipeline.py::test_abn_string_does_not_produce_phone_span` passes
- [ ] `test_validators.py::TestPhoneRegex::test_no_match_inside_abn` passes
- [ ] `pytest tests/ -v` reports `58 passed, 0 failed`
- [ ] Mock-backend 500-doc Gretel baseline still shows **0 leaks** (no regression)
- [ ] Ruff lint passes on changed files

### US-002: Pull Llama-3.1-8B-Instruct and bench it
**Description:** As an MLE, I need to bench the exact model class the Wiest paper uses so the prompt tuning is aligned and we measure real sensitivity, not a stand-in.

**Acceptance Criteria:**
- [ ] `ollama pull llama3.1:8b` completes; model listed in `ollama list`
- [ ] Run `scale-tests/run_library_benchmark.py` with `PIIR_OLLAMA_MODEL=llama3.1:8b` on 100-doc Gretel fixture, `--limit 100`
- [ ] Run dir landed in `scale-tests/runs/<timestamp>-ollama-llama31-gretel100/`
- [ ] `summary.json` written; sensitivity computed as `(checked - leaks) / checked`
- [ ] If sensitivity ≥99.4% → mark Gretel-pass=true and **skip to US-006** (medical fixture)
- [ ] If sensitivity <99.4% → proceed to US-003

### US-003: Improve the address-extraction prompt
**Description:** As an MLE, I need address detection to lift from 90.9% recall toward ≥99% so the weakest category stops dragging the overall sensitivity. Only triggered if US-002 didn't hit 99.4%.

**Acceptance Criteria:**
- [ ] Edit `pii_redactor/prompts.py` — add explicit street-name/suburb/postcode/state context cues
- [ ] Add 2–3 few-shot examples of compound-sentence addresses (e.g., "located at Suite 378, Yolanda Mountain, Burkeberg")
- [ ] Re-bench on 100-doc Gretel with Llama-3.1-8B; new run dir under `scale-tests/runs/`
- [ ] Per-category leak table written to run dir's `REPORT.md`
- [ ] Address recall ≥99% on this run
- [ ] Overall sensitivity ≥99.4% → mark Gretel-pass=true; **skip to US-006**
- [ ] If still <99.4% → proceed to US-004

### US-004: Stand up llama.cpp server with GBNF grammar (conditional)
**Description:** As an MLE, I need a llama.cpp backend with GBNF-constrained JSON output for the cleanest parse — matches Wiest's exact pipeline. Only triggered if US-002 + US-003 still fall short of 99.4%.

**Acceptance Criteria:**
- [ ] llama.cpp server running locally with `Llama-3.1-8B-Instruct.Q4_K_M.gguf` (or comparable quant)
- [ ] `pii_redactor/grammar.py` GBNF wired through `LlamaCppClient` backend
- [ ] Set `PIIR_BACKEND=llama_cpp`; re-bench 100-doc Gretel
- [ ] Run dir landed in `scale-tests/runs/<timestamp>-llamacpp-gbnf-gretel100/`
- [ ] Overall sensitivity ≥99.4% → mark Gretel-pass=true
- [ ] llama.cpp setup notes added to `scale-tests/RUNBOOK.md` (replacing typo'd paths)

### US-005: Generate synthetic medical PII fixture
**Description:** As an MLE, I need a 50-doc medical narrative fixture with labeled PII so we can claim apples-to-apples Wiest comparison. Generated synthetically via Claude Sonnet (cheap, no PhysioNet wait).

**Acceptance Criteria:**
- [ ] `scale-tests/fixtures/synthetic-medical-50/` created
- [ ] `documents.jsonl` — 50 records, each a clinical-note-style narrative (300–800 chars) with embedded PII
- [ ] `expected_labels.jsonl` — ground-truth labels per doc, schema-compatible with existing benchmark script
- [ ] PII categories covered: patient name, MRN, DOB, address, phone, doctor name, hospital name, dates
- [ ] Generation script `scale-tests/generate_synthetic_medical.py` committed (reproducible)
- [ ] At least 10 of 50 docs include AU identifiers (Medicare, IHI) to stay within product scope

### US-006: Bench medical fixture on the best-performing backend
**Description:** As an MLE, I need to validate that the Gretel-passing config also clears 99.4% on the medical fixture so the Wiest-grounded claim holds for the paper's actual domain.

**Acceptance Criteria:**
- [ ] Bench script run on `synthetic-medical-50` using whichever backend passed in US-002/003/004
- [ ] Run dir landed in `scale-tests/runs/<timestamp>-<backend>-medical50/`
- [ ] `summary.json` shows sensitivity ≥99.4% on this fixture
- [ ] Per-category recall reported in `REPORT.md`
- [ ] If medical sensitivity <99.4% but Gretel was ≥99.4% — flag domain-shift issue and write `.planning/MEDICAL-GAP.md` noting categories that regressed

### US-007: Update README claims and land the pass gate
**Description:** As a user reading the README, I want the sensitivity claim to match measured reality so the project is honest about what it ships.

**Acceptance Criteria:**
- [ ] `README.md` line 25: replace "Llama-3-8B-Instruct hits 98.2% accuracy and 99.4% sensitivity on the paper's medical PII benchmark" with verified numbers, model used, fixture name, run dir reference
- [ ] Add a "Measured performance (2026-05-XX)" subsection citing the actual run
- [ ] Create `.planning/PASS-GATE.md` listing: model used, fixture(s), per-category recall, overall sensitivity, run dir paths, date
- [ ] `tests/test_pipeline.py` re-runs green (no regression from prompt edits)

## 4. Functional Requirements

- **FR-1:** The eval harness must compute sensitivity as `(leak_checked_counts.total - leak_count_total) / leak_checked_counts.total` per run, written to `summary.json`.
- **FR-2:** The autonomous loop must execute workstreams in order US-002 → US-003 → US-004, with **early exit** as soon as any run's Gretel sensitivity ≥99.4%.
- **FR-3:** US-005 (medical fixture generation) must run regardless of where Gretel passes — it's required for the apples-to-apples claim.
- **FR-4:** The README update (US-007) must NOT happen until BOTH Gretel and Medical fixtures show ≥99.4% — partial passes get flagged in `.planning/MEDICAL-GAP.md` instead.
- **FR-5:** Every bench run must produce: `summary.json`, `results.jsonl`, `REPORT.md` in its run dir.
- **FR-6:** No external paid API calls during eval (`$0 cost cap`). Synthetic-fixture generation may use Claude Sonnet via the Anthropic SDK if available offline-key'd; otherwise mock the generation.
- **FR-7:** All file edits must be atomic commits; each US gets its own commit message with run-dir reference.

## 5. Non-Goals (Out of Scope)

- **No GPU runs.** CPU-only on the Ryzen 7 7840HS. 13B+ models excluded.
- **No SaaS or remote LLM APIs** for inference (Anthropic SDK only permitted for synthetic-fixture generation, not redaction).
- **No new PII categories** added. Existing 18 categories remain the surface.
- **No MIMIC-III procurement** (rejected as too slow — synthetic medical chosen instead).
- **No GBNF wire-up if not needed** — workstream US-004 is conditional, only runs if US-002 + US-003 don't hit 99.4%.
- **No throughput/latency tuning** — current ~5,400 docs/day on CPU is acceptable for MVP eval; production performance is a separate PRD.
- **No FastAPI changes** — service layer stays as-is; this PRD only touches the detection layer + eval.
- **No medical compliance certification** — synthetic data, no real PHI.

## 6. Technical Considerations

- **Model:** Llama-3.1-8B-Instruct (Q4_K_M quant). RAM budget ~6GB; should fit on 27GB RAM jimbot.
- **Backend switch:** `PIIR_BACKEND` env var controls Ollama vs llama.cpp; existing code in `pii_redactor/config.py` already supports both.
- **GBNF grammar:** Already drafted in `pii_redactor/grammar.py`; needs only the HTTP wire-up to llama.cpp's `/completion` endpoint with `grammar` parameter.
- **Bench script:** `scale-tests/run_library_benchmark.py` already produces the metrics we need — no script changes required.
- **Fixture schema:** `documents.jsonl` (id, text) + `expected_labels.jsonl` (id, labels: [{category, value, valid}]) — established schema, just need to match it for synthetic medical.
- **Address prompt edits** must preserve token budget (4000-char chunk; ~600-token system prompt budget).
- **The 2 failing regex tests** mean current phone regex matches `12 345 678 901` (an 11-digit ABN-style pattern); fix likely involves adding an explicit length cap or anchoring around AU phone prefixes (`04`, `02`, `03`, `+61`).

## 7. Success Metrics

| Metric | Target | Verified by |
|--------|--------|-------------|
| Unit tests passing | 58 / 58 | `pytest tests/` |
| Gretel-100 sensitivity (Llama-3.1-8B) | ≥99.4% | `summary.json` from bench run |
| Medical-50 sensitivity | ≥99.4% | `summary.json` from medical bench |
| Address category recall | ≥99% (up from 90.9%) | Per-category in `REPORT.md` |
| Mock-baseline regression | 0 leaks on regex-checkable PII | `pytest`-style mock benchmark |
| README accuracy | Claim cites real run-dir + date | `git diff README.md` |
| `.planning/PASS-GATE.md` exists | Yes | File present, lists all run dirs |
| External API spend | $0 | Cost ledger / no API key used |

## 8. Stop Condition (Autonomous Loop)

**Early-exit policy (per user choice):**

1. Run US-001 (regex fixes) — always required, blocks the rest
2. Run US-002 (Llama-3.1-8B bench) — measure Gretel sensitivity
3. **If Gretel ≥99.4% → jump to US-005** (skip prompt + GBNF)
4. Otherwise, run US-003 (address prompt) — re-bench
5. **If Gretel ≥99.4% → jump to US-005**
6. Otherwise, run US-004 (llama.cpp + GBNF) — re-bench
7. **If Gretel ≥99.4% → jump to US-005**
8. If after all three steps Gretel still <99.4% → halt with a structured report at `.planning/STALL-REPORT.md` listing what was tried, final recall per category, and the smallest miss; no README update.
9. US-005 (medical fixture generation) + US-006 (medical bench) always run after Gretel passes.
10. US-007 (README + pass gate) only runs if BOTH Gretel-100 ≥99.4% AND Medical-50 ≥99.4%.

## 9. Open Questions

- **Q1:** If Llama-3.1-8B is too slow on CPU (e.g., >30s/doc), should we drop to Llama-3.2-3B as a fallback? **Default decision:** yes — note in run report and continue; sensitivity gap may widen but throughput becomes acceptable.
- **Q2:** Synthetic medical fixture generation — use Claude Sonnet 4.6 or Opus 4.7? **Default decision:** Sonnet 4.6 — cheaper, fast enough, generation quality adequate for synthetic labels.
- **Q3:** Address-prompt edits — single mega-prompt or split into 2 calls (one for structured PII, one for narrative)? **Default decision:** single prompt with stronger address section; minimal disruption to existing pipeline.
- **Q4:** If 99.4% on Gretel passes via Q4_K_M quant but US-004 GBNF is needed for Medical, should both backends be retained? **Default decision:** yes — config-driven backend selection already supports this; document both in README.

## 10. References

- Wiest IC, Leßmann ME, Wolf F, et al. *Deidentifying Medical Documents with Local, Privacy-Preserving Large Language Models: The LLM-Anonymizer.* NEJM AI 2024. DOI: [10.1056/AIdbp2400537](https://ai.nejm.org/doi/full/10.1056/AIdbp2400537)
- Baseline run: `scale-tests/runs/20260517-150856-ollama-qwen25-gretel100-wiest-bench/summary.json`
- 30-doc preliminary: `scale-tests/runs/20260517-145854-ollama-qwen25-gretel30/`
- Mock baseline: `scale-tests/runs/20260517-145837-mock-gretel500-baseline/`
- README claim location: `C:/Users/j_car/KnowledgeGraph/tools/pii-redactor/README.md:25`
