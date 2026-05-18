# GitHub push — manual unblock required

## Status
- Repo created: https://github.com/Jimmycarroll2021/pii-redactor
- `origin` remote added: `git@github.com:Jimmycarroll2021/pii-redactor.git`
- Push BLOCKED by GitHub secret-scanning push-protection.

## Blocking secret
GitHub flagged a Slack token pattern in commit `17906f6`:
- Path: `scale-tests/fixtures/gretel-pii-masking-en-500/documents.jsonl:438`
- Pattern: `xoxb-591525709727-932389906847-HsoN00FqfT0IZRjO31lwYX6P`
- This is a SYNTHETIC test fixture from the Gretel PII-masking dataset — the dataset is intentionally full of redactable secret-shaped strings. It is NOT a real Slack token.

## Unblock options

### Option A — Unblock via GitHub UI (recommended, fast)
Visit the unblock URL and confirm the secret is a test fixture:
https://github.com/Jimmycarroll2021/pii-redactor/security/secret-scanning/unblock-secret/3DsWaJG8v9fp2SixnDvlcPTDrIy

Reason to give: "Used in tests" — this is a synthetic fixture from the public Gretel PII-masking dataset, not a real credential.

Then push:
```bash
cd C:/Users/j_car/KnowledgeGraph/tools/pii-redactor
git push origin main
git push origin v0.1.2
```

### Option B — Rewrite history to remove the fixture
Destructive — only do this if Option A is refused. Requires `git filter-repo`.

## After successful push
- Run `gsd-watchdog`-style verification: `gh repo view Jimmycarroll2021/pii-redactor`
- Then create the release: `gh release create v0.1.2 --title "v0.1.2 — Wiest-grounded sensitivity" --notes-file CHANGELOG.md dist/pii_redactor-0.1.2-py3-none-any.whl dist/pii_redactor-0.1.2.tar.gz`
