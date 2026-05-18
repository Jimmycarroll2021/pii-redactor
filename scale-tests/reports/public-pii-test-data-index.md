# Public/Synthetic PII Test Data Index

**Generated:** 2026-05-03

## Purpose

This file lists the PII test datasets now available locally for the project. These are public or synthetic benchmark sources, not private real-world PII dumps.

## Local Test Fixtures

| Source | Fixture | Docs | Notes |
|---|---|---:|---|
| Kaggle-derived PII Detection mirror | scale-tests/fixtures/kaggle-pii-7k-converted | 945 | Student-writing PII labels from public mirror. Official Kaggle competition download remains blocked until competition rules are accepted. |
| AI4Privacy OpenPII English | scale-tests/fixtures/ai4privacy-openpii-english-500 | 500 | Synthetic English PII masking examples, mainly emails and usernames mapped to patient_id. |
| Gretel PII Masking English | scale-tests/fixtures/gretel-pii-masking-en-500 | 500 | Synthetic domain documents with names, DOBs, addresses, emails, phones, IDs, URLs. |
| Project synthetic AU PII 2k | scale-tests/fixtures/synthetic-2000-seed43 | 2000 | Project-generated Australian government/medical identifiers. |
| Contextual qwen proof | scale-tests/fixtures/pii-context-proof-20260503 | 6 | Hand-built clinical/case/form/referral contexts. |
| Hidden 40-page proof | scale-tests/fixtures/pii-hidden-middle-40page-20260503 | 1 | PII buried on page 21 of 40. |

## Raw External Downloads

| Source | Local raw path |
|---|---|
| Kaggle-derived Hugging Face mirror | scale-tests/external/kaggle-pii-detection-7k/train.json |
| AI4Privacy OpenPII English validation | scale-tests/external/ai4privacy-pii-masking-300k/1english_openpii_8k.jsonl |
| Gretel PII Masking EN test parquet | scale-tests/external/gretel-pii-masking-en-v1/test.parquet |
| Finance synthetic PII parquet | scale-tests/external/finance-synthetic-pii/test.parquet |

## Smoke Test Results

| Fixture | Run | Docs | Backend | Checked leaks | Result |
|---|---|---:|---|---:|---|
| Kaggle converted | scale-tests/runs/20260503-kaggle-pii-7k-converted-mock-945docs | 945 | mock | 76 | Fail - useful gap dataset |
| AI4Privacy English 500 | scale-tests/runs/20260503-ai4privacy-openpii-english-500-mock | 500 | mock | 418 | Fail - username/ID gap dataset |
| Gretel English 500 | scale-tests/runs/20260503-gretel-pii-masking-en-500-mock | 500 | mock | 235 | Fail - ID/phone gap dataset |

## Current Meaning

These datasets are now available for testing and fixing. The failures are useful: they show where the current detector does not generalize beyond the Australian structured/contextual proof set.

## Converter Scripts

- Kaggle converter: scale-tests/convert_kaggle_pii.py
- Public dataset converter: scale-tests/convert_public_pii_datasets.py

## Official Kaggle Access

Kaggle auth is configured locally, but the official competition download returns 403 Forbidden because the Kaggle account has not accepted/entered the competition rules. Once that is accepted in the browser, the official files can be downloaded with the saved token.
