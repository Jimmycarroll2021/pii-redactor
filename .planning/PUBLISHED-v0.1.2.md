# pii-redactor v0.1.2 — Publish Report

**Date:** 2026-05-18
**Tag SHA:** `d9f8974c749a9bf463fdb92f73b6a1d97f9de26f`

## Status — Partial success

| Target | Status | URL / Note |
|---|---|---|
| PyPI | FAIL | 403 Forbidden from upload.pypi.org/legacy/. Halted after one attempt per safety rules. .pypirc structure verified (username + password fields present, leading-whitespace indented), suggesting expired/invalid token or scope mismatch. Token rotation required. |
| Docker Hub | SKIPPED | No `docker login` session detected (`docker info` returned no username). Not retried — no TTY for interactive login per safety rules. |
| HuggingFace Space | SUCCESS | https://huggingface.co/spaces/JimmyBhoy/pii-redactor (commit `0266c91`) |
| GitHub repo | CREATED, push BLOCKED | https://github.com/Jimmycarroll2021/pii-redactor — empty. Push blocked by secret-scanning push-protection on commit `17906f6` (Slack-token-shaped string at `scale-tests/fixtures/gretel-pii-masking-en-500/documents.jsonl:438`, false-positive — synthetic Gretel fixture). Unblock URL + manual steps in `.planning/GITHUB-MANUAL.md`. |
| GitHub Release | BLOCKED | Depends on push succeeding. `gh release create` returned 422 "Repository is empty". |

## Artefact checksums (SHA256)
- `pii_redactor-0.1.2-py3-none-any.whl`: `f9889cc759c2db6bac56fe8afd1e946ffa7d0622b16feb8f640ffcd5a9e172bc`
- `pii_redactor-0.1.2.tar.gz`: `b7de864a193a29721e87526a06153bc502174bd4892f9124c8ebc6a1191251e4`

## Install instructions (after PyPI fix)
```bash
pip install pii-redactor==0.1.2
```

Until PyPI is fixed, install from wheel:
```bash
pip install dist/pii_redactor-0.1.2-py3-none-any.whl
```

## Follow-ups for Jim
1. **PyPI** — rotate the API token at https://pypi.org/manage/account/token/, update `~/.pypirc` (keep `username = __token__` and `password = pypi-...` indented under `[pypi]`), then re-run:
   ```bash
   cd C:/Users/j_car/KnowledgeGraph/tools/pii-redactor
   .venv/Scripts/python.exe -m twine upload dist/pii_redactor-0.1.2-py3-none-any.whl dist/pii_redactor-0.1.2.tar.gz
   ```
2. **GitHub push** — visit the unblock URL in `.planning/GITHUB-MANUAL.md` to allow the synthetic fixture, then:
   ```bash
   git push origin main
   git push origin v0.1.2
   gh release create v0.1.2 --title "v0.1.2 — Wiest-grounded sensitivity" \
     --notes-file CHANGELOG.md \
     dist/pii_redactor-0.1.2-py3-none-any.whl dist/pii_redactor-0.1.2.tar.gz
   ```
3. **Docker Hub** (optional) — `docker login` interactively, then:
   ```bash
   docker tag pii-redactor:0.1.2 jimmybhoy/pii-redactor:0.1.2
   docker tag pii-redactor:0.1.2 jimmybhoy/pii-redactor:latest
   docker push jimmybhoy/pii-redactor:0.1.2
   docker push jimmybhoy/pii-redactor:latest
   ```
4. **HF Space README** — the README.md is missing YAML frontmatter; the Space will still build but Hugging Face emitted a warning. Add a YAML header:
   ```yaml
   ---
   title: PII Redactor
   emoji: 🔒
   colorFrom: indigo
   colorTo: blue
   sdk: gradio
   sdk_version: 4.44.0
   app_file: app.py
   pinned: false
   ---
   ```
