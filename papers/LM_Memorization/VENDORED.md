# VENDORED — LM_Memorization

Read-only vendored snapshot of the reference implementation for Carlini et al. 2021 ("Extracting Training Data from Large Language Models").

| Field | Value |
|---|---|
| Upstream | https://github.com/ftramer/LM_Memorization |
| Author | Florian Tramèr (Carlini et al. 2021 third author) |
| License | MIT (Copyright © 2021 Florian Tramèr — see `LICENSE`) |
| Commit | `baafa173046978e3d882fbbb9adbc7af5bd2f701` |
| Commit date | 2022-09-21 |
| Vendored on | 2026-05-21 |
| Vendored by | `redact-au` (Jim Carroll) |

## Why this is vendored

We re-implement Carlini et al. 2021's scoring metrics for the `redact-au-verify` attestation layer. To keep the implementation defensibly faithful — and auditable by procurement teams — this reference implementation is vendored as a read-only ground-truth artefact.

Citation comments in `redact-au/verify/src/redact_au_verify/canary_carlini.py` point to specific line numbers in `extraction.py` of this snapshot for each scoring metric.

## What it is NOT

- ❌ **Not** imported as a Python dependency. Our `canary_carlini.py` is a fresh implementation; this snapshot is documentation/reference only.
- ❌ **Not** kept live with upstream — we do not `git pull` updates. To refresh, replace the directory and bump the commit SHA above.
- ❌ **Not** intended for execution in our test suite. Treat as static reference material.

## Mapping from `extraction.py` → our `canary_carlini.py`

| `extraction.py` reference | Our implementation |
|---|---|
| `calculatePerplexity()` (lines 20-29) — `exp(loss)` | `CarliniCanaryScorer._perplexity()` |
| `metric = -np.log(scores["XL"])` (line 171) | Headline `perplexity` score |
| `metric = np.log(scores["S"]) / np.log(scores["XL"])` (line 178) | `CarliniScores.perplexity_ratio` |
| `metric = np.log(scores["Lower"]) / np.log(scores["XL"])` (line 185) | `CarliniScores.case_sensitivity_ratio` |
| `metric = scores["zlib"] / np.log(scores["XL"])` (line 192) | `CarliniScores.zlib_ratio` |

## License compliance

MIT requires only attribution. The above table + this provenance note + the LICENSE file copied alongside satisfy that. Our `canary_carlini.py` retains a `# Reference:` header pointing here.
