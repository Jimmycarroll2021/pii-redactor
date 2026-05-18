# Publish Readiness — v0.1.2

Generated 2026-05-18 during Phase 5 of the release plan. Phase 6 (actual upload) is **HALTED** until all three credentials are confirmed.

## Status

| Target | Status | Account | Notes |
|---|---|---|---|
| **PyPI** | MISSING | — | No `~/.pypirc`, no `TWINE_USERNAME`/`TWINE_PASSWORD`, no `PYPI_API_TOKEN`, no `UV_PUBLISH_TOKEN` in env |
| **HuggingFace** | READY | `JimmyBhoy` | `HF_TOKEN` is set; `hf auth whoami` returns user + 3 orgs |
| **GitHub** | READY | `Jimmycarroll2021` | `gh auth status` OK; scopes include `repo` (sufficient for `gh release create`) |
| **Docker Hub** | UNKNOWN | — | Not requested in cred-check, but Phase 6 step 3 expects a configured user. `docker login` status not verified — recommend manual check before push. |

## What to set if missing

### PyPI (required for Phase 6 step 1-2)
Pick one:

```bash
# Option A — env vars (one-shot)
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgENdGVzdC5weXBpLm9yZ...   # your real token

# Option B — persist in ~/.pypirc
cat > ~/.pypirc <<'EOF'
[distutils]
index-servers = pypi

[pypi]
username = __token__
password = pypi-AgENdGVzdC5weXBpLm9yZ...
EOF
chmod 600 ~/.pypirc
```

Get a token at https://pypi.org/manage/account/token/ (scope: project `pii-redactor` after first manual upload, or "Entire account" for first publish).

### HuggingFace (ready)
`HF_TOKEN` already set in env. Token rotation if needed:
```bash
hf auth login   # interactive
```

### GitHub (ready)
Authenticated as `Jimmycarroll2021`. No action required.

### Docker Hub (recommend confirming)
Before Phase 6 step 3:
```bash
docker login -u <dockerhub-user>   # prompts for token/password
```

If `DOCKER_HUB_USER` is not configured in env, the plan's `docker tag pii-redactor:0.1.2 jimmybhoy/pii-redactor:0.1.2` assumes `jimmybhoy` — confirm that matches your Docker Hub account.

## Phase 6 gate

Cannot proceed automatically. Phase 6 (twine upload, docker push, HF Space update, GitHub release) requires:

1. **PyPI token** — block. Set `TWINE_PASSWORD` then re-run release flow from "twine upload" step.
2. **Docker Hub login** — verify with `docker info | grep Username` before push.
3. Re-run from `twine upload dist/*` once both are set.

## Artefacts ready to publish (Phase 3-4 completed)

- `dist/pii_redactor-0.1.2-py3-none-any.whl` (35 KB, `twine check` PASSED)
- `dist/pii_redactor-0.1.2.tar.gz` (40 KB, `twine check` PASSED)
- Docker image: `pii-redactor:0.1.2` (sha256:b3bafdf386a5, 258 MB)
- Git tag: `v0.1.2` on commit `d9f8974` (local only — not pushed)

## Next user action

Set the PyPI token (and confirm Docker Hub login), then say "Phase 6 go" and the agent will execute upload steps 1-6.
