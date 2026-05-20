# References

This document catalogues every academic paper, framework, and standard that
`pii-redactor-au` and the `redact-au` verification stack build on, plus the file
in our codebase that implements each.

**Last verified:** 2026-05-21

## Reference assets layout

| Location | Role | Format |
|----------|------|--------|
| `papers/` | Authoritative source archives | LaTeX tar.gz (arxiv) + USENIX Security final |
| `docs/references/` | Reading copies + this catalogue | arxiv preprint PDFs |
| `papers/LM_Memorization/` | Reference implementation (vendored) | Python (read-only, MIT-attributed) |

For the Carlini 2021 paper specifically: `papers/sec21-carlini-extracting.pdf`
is the USENIX Security final and authoritative;
`docs/references/carlini-2021-extracting.pdf` is the arxiv preprint kept for
offline reading convenience. The reference implementation lives at
`papers/LM_Memorization/` and is mirrored by `redact-au/verify/src/redact_au_verify/canary_carlini.py`.

## Academic papers

### Methodology + evaluation

- **Wiest et al. (2024) — "Deidentifying Medical Documents with Local, Privacy-Preserving Large Language Models: The LLM-Anonymizer"** — NEJM AI. DOI: [10.1056/AIdbp2400537](https://ai.nejm.org/doi/full/10.1056/AIdbp2400537). PDF: [`AIdbp2400537.pdf`](./AIdbp2400537.pdf).
  - **Implements:** entire evaluation methodology + 99.4% sensitivity bar.
  - **Used in:** every release scorecard; frozen-bench gate; heartbeat target metric.

### Privacy attacks (verification layer)

- **Carlini et al. (2021) — "Extracting Training Data from Large Language Models"** — USENIX Security 2021. arxiv: [2012.07805](https://arxiv.org/abs/2012.07805). PDF: [`carlini-2021-extracting.pdf`](./carlini-2021-extracting.pdf). USENIX final: `../../papers/sec21-carlini-extracting.pdf`. Reference impl: [`papers/LM_Memorization/`](../../papers/LM_Memorization/) (MIT-licensed, vendored snapshot of github.com/ftramer/LM_Memorization at commit `baafa173`).
  - **Implements §3 (insertion + extraction):** `redact-au/verify/src/redact_au_verify/canary.py` — quickcheck mode (binary string-match against generated output).
  - **Implements §6 (scoring metrics — perplexity ratio + zlib + case sensitivity):** `redact-au/verify/src/redact_au_verify/canary_carlini.py`.
  - Both implementations expose the same `Canary` dataclass; the reporter picks the mode via `canary_mode="quickcheck"` (default) or `canary_mode="carlini"`.

- **Shokri et al. (2017) — "Membership Inference Attacks Against Machine Learning Models"** — IEEE S&P 2017. arxiv: [1610.05820](https://arxiv.org/abs/1610.05820). PDF: [`shokri-2017-mia.pdf`](./shokri-2017-mia.pdf).
  - **Implements §4 (confidence-threshold baseline):** `redact-au/verify/src/redact_au_verify/membership_inference.py` (FAITHFUL — published baseline variant, computes ROC AUC via Mann-Whitney U with tie handling).
  - **§5 (K-shadow-model attack):** deferred to Phase 7 Wave 4. See `redact-au/.planning/phases/07-benchmarking-rigor/07-PLAN.md`. The current threshold attack is the honest published baseline; full shadow-model adds complexity (K models on disjoint splits + meta-classifier) without changing the headline finding for MVP attestation.

### Model compression + adaptation

- **Hu et al. (2022) — "LoRA: Low-Rank Adaptation of Large Language Models"** — ICLR 2022. arxiv: [2106.09685](https://arxiv.org/abs/2106.09685). PDF: [`hu-2022-lora.pdf`](./hu-2022-lora.pdf).
  - **Implements:** rank-decomposition adapter on the `openai/privacy-filter` base, loaded via the PEFT library.
  - **Used in:** `pii_redactor/hybrid/finetuned_backend.py`.

- **Lin et al. (2024) — "AWQ: Activation-aware Weight Quantization for On-Device LLM Compression and Acceleration"** — MLSys 2024 (Best Paper). arxiv: [2306.00978](https://arxiv.org/abs/2306.00978). PDF: [`lin-2024-awq.pdf`](./lin-2024-awq.pdf).
  - **Implements:** 4-bit weight quantization of Llama-3.1-8B for the Tier-2 narrative-NER pass.
  - **Used in:** `pii_redactor/hybrid/vllm_pass.py` (consumes the AWQ-quantized model `llama3.1-8b-awq` served via vLLM).

- **Frantar et al. (2024) — "MARLIN: Mixed-Precision Auto-Regressive Parallel Inference on Large Language Models"** — arxiv: [2408.11743](https://arxiv.org/abs/2408.11743). PDF: [`frantar-2024-marlin.pdf`](./frantar-2024-marlin.pdf).
  - **Note:** arxiv ID `2408.11743` verified 2026-05-21. The fuller title is "MARLIN: Mixed-Precision Auto-Regressive Parallel Inference on Large Language Models", not "Marlin FP16 W4A16 GEMM kernel" as informally referred to internally. Same authors (Frantar, Castro, Chen, Hoefler, Alistarh) and same kernel — the paper covers both the kernel and the batched-inference scheduler that ships in vLLM as `awq_marlin`.
  - **Implements:** the AWQ-Marlin kernel path that gives ~4× speedup over plain AWQ in batched serving.
  - **Used in:** `pii_redactor/hybrid/vllm_pass.py` via the vLLM service configured with `--quantization=awq_marlin`.

## Reference implementations

Vendored ground-truth implementations cross-checked against our re-implementations.

| Paper | Reference impl | Vendored at | Used by |
|-------|----------------|-------------|---------|
| Carlini 2021 (extraction) | github.com/ftramer/LM_Memorization (MIT, Florian Tramèr) | [`papers/LM_Memorization/`](../../papers/LM_Memorization/) — commit `baafa173`, 2026-05-21 | `redact-au/verify/src/redact_au_verify/canary_carlini.py` |

The vendored snapshot is **read-only** — citation comments in `canary_carlini.py` point at specific line numbers in `papers/LM_Memorization/extraction.py` for each scoring metric. See `papers/LM_Memorization/VENDORED.md` for the provenance + mapping table.

## AU regulatory + standards

These are gov-published, frequently revised, and authoritative-by-URL. We link
rather than cache to avoid stale copies; retrieval date below records the
version we built against.

- **Privacy Act 1988 + Australian Privacy Principles (APP 1-13)** — Office of the Australian Information Commissioner (OAIC). [Source](https://www.oaic.gov.au/privacy/australian-privacy-principles). Retrieved 2026-05-21.
  - **Used in:** `redact-au/verify/src/redact_au_verify/reporter.py` (APP 11 / 11.2 / 12 mapping in the attestation PDF + Markdown templates).

- **PSPF (Protective Security Policy Framework)** — Attorney-General's Department, 2025 release. [Source](https://www.protectivesecurity.gov.au/publications-library/policy-9-access-to-information). Retrieved 2026-05-21.
  - **Used in:** sector-suite PSPF tier labelling (OFFICIAL / OFFICIAL: Sensitive / PROTECTED) in `redact-au/benchmarks/` outputs and grant deliverables under `redact-au/grants/`.

- **ASD Essential Eight maturity model** — Australian Cyber Security Centre (ACSC). [Source](https://www.cyber.gov.au/resources-business-and-government/essential-cyber-security/essential-eight/essential-eight-maturity-model). Retrieved 2026-05-21.
  - **Used in:** `redact-au/grants/IRAP-scoping.md` (Maturity Level 2 target for IRAP).

- **ISM (Information Security Manual)** — ACSC. [Source](https://www.cyber.gov.au/ism). Retrieved 2026-05-21.
  - **Used in:** `redact-au/grants/IRAP-scoping.md` (control mapping for PROTECTED tier).

- **NEHTA / ADHA Individual Healthcare Identifier (IHI) specification** — Australian Digital Health Agency. [Source](https://www.digitalhealth.gov.au/healthcare-providers/individual-healthcare-identifiers-ihi). Retrieved 2026-05-21.
  - **Used in:** `pii_redactor/validators.py` (`validate_ihi` — 16-digit Luhn-checksum verifier).

- **RACGP "De-identifying data" information sheet** — Royal Australian College of General Practitioners. [Source](https://www.racgp.org.au/running-a-practice/security/protecting-information/de-identification) (searched at racgp.org.au — final URL may move; the de-identification handbook is the canonical reference). Retrieved 2026-05-21.
  - **Used in:** Phase 2 medical-narrative corpus design guidance + sector-bench-builder template for the health sector.

- **ABR ABN Lookup web service** — Australian Business Register. [Source](https://abr.business.gov.au/Tools/AbnLookup) (web service docs: <https://abr.business.gov.au/Tools/WebServices>). Retrieved 2026-05-21.
  - **Used in:** `pii_redactor/validators.py` (`validate_abn` — mod-89 weighted checksum) and the ASIC companies fixture under `services/sector-bench-builder/data/au-real-identifiers/`.

- **ATO TFN algorithm (mod-11 weighted-sum)** — Australian Taxation Office. The ATO does not publish the checksum weights in a single canonical document; the mod-11 weighted-sum with weight vector `[1, 4, 3, 7, 5, 8, 6, 9, 10]` for the 9-digit format is the standard implementation widely documented across tax-software vendors and matches the ATO test-TFN behaviour. Retrieved 2026-05-21.
  - **Used in:** `pii_redactor/validators.py` (`validate_tfn` — supports both legacy 8-digit and current 9-digit formats).

- **ASIC ACN algorithm (mod-10 weighted-sum)** — Australian Securities & Investments Commission. ACN is the 9-digit identifier underpinning the ABN's check; the standard mod-10 weighted-sum is the published verification routine. Used as a sanity check after ABN extraction. Retrieved 2026-05-21.
  - **Used in:** `pii_redactor/validators.py` (ACN check inside `validate_abn` plus standalone ACN validators).

## Reference layout

`docs/references/` contains:

- This `REFERENCES.md` catalogue.
- One PDF per academic paper (named by citekey: `<author>-<year>-<topic>.pdf`).
- AU framework documents are linked (URLs) rather than cached, since government
  sites maintain canonical versions and frequently update with new policy releases.

## Verification (for procurement teams)

Every claim in the pitch deck, model card, or attestation report that uses
methodology from these references is footnoted with the matching citekey.
Procurement teams (and auditors) can cross-check by:

1. Looking up the citekey in this file.
2. Reading the linked PDF (academic) or URL (AU framework).
3. Reading the implementing file in our codebase — each carries a `# References:`
   header comment block listing the citekeys it depends on.

This catalogue plus the per-file citation headers form a defensible audit trail
from "claim in the pitch" all the way down to "line of code that ships the
behaviour".
