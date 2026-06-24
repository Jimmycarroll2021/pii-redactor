"""Hybrid regex+LLM detection tests.

Tests that the regex pre-pass catches structured AU identifiers independently
of the LLM, and that results from both paths merge without duplicates.
"""
import json
import re

import pytest

from pii_redactor.detector import PIIDetector
from pii_redactor.models import PIICategory, PIISpan
from pii_redactor.validators import regex_first_pass


class NoopClient:
    """LLM stub that never detects anything — isolates the regex pre-pass."""

    name = "noop"

    def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return '{"pii": []}'


class NameDetectingClient:
    """LLM stub that detects 'First Last' name patterns but nothing else."""

    name = "name_mock"

    def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        matches = re.findall(r'"""(.+?)"""', user_prompt, re.DOTALL)
        text = matches[-1] if matches else ""
        names = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
        return json.dumps({"pii": [{"category": "name", "value": n} for n in names]})


def _make_detector(client, use_regex_prepass: bool = True) -> PIIDetector:
    return PIIDetector(llm_client=client, use_grammar=False, use_regex_prepass=use_regex_prepass)


# ---------------------------------------------------------------------------
# Regex pre-pass catches structured fields without LLM
# ---------------------------------------------------------------------------

class TestRegexPrepassAlone:
    def test_catches_valid_tfn(self):
        det = _make_detector(NoopClient())
        spans = det.detect("TFN: 123 456 782")
        cats = {s.category for s in spans}
        assert PIICategory.TFN in cats

    def test_catches_abn_with_spaces(self):
        det = _make_detector(NoopClient())
        spans = det.detect("ABN 33 051 775 556")
        assert any(s.category == PIICategory.ABN for s in spans)

    def test_catches_medicare(self):
        det = _make_detector(NoopClient())
        spans = det.detect("Medicare: 2957 20197 1")
        assert any(s.category == PIICategory.MEDICARE for s in spans)

    def test_catches_email(self):
        det = _make_detector(NoopClient())
        spans = det.detect("Send to jdoe@example.gov.au please")
        assert any(s.category == PIICategory.EMAIL for s in spans)

    def test_catches_au_phone(self):
        det = _make_detector(NoopClient())
        spans = det.detect("Call 0412 345 678 for details")
        assert any(s.category == PIICategory.PHONE for s in spans)

    def test_disabled_prepass_misses_structured(self):
        det = _make_detector(NoopClient(), use_regex_prepass=False)
        spans = det.detect("TFN: 123 456 782")
        # NoopClient returns nothing; prepass disabled → nothing detected
        assert spans == []


# ---------------------------------------------------------------------------
# Checksum validation is fail-CLOSED (VULN-01 / SEC-01)
#
# A token shaped like a regulated ID but failing its checksum is *suspected*
# PII, not safe: it is still redacted (so no cleartext residue survives) and
# flagged validator_passed=False / needs_review=True. A valid ID passes cleanly
# without a review flag.
# ---------------------------------------------------------------------------

class TestChecksumFiltering:
    def test_invalid_tfn_redacted_and_flagged(self):
        # 123 456 789 has wrong checksum — must NOT be dropped (would leak the
        # tail via a shorter overlapping match). It is retained, flagged.
        det = _make_detector(NoopClient())
        spans = det.detect("TFN: 123 456 789")
        covering = [s for s in spans if s.start <= 5 and s.end >= 16]
        assert covering, "malformed TFN must remain covered by a redaction span"
        assert any(s.needs_review and s.validator_passed is False for s in spans)

    def test_invalid_abn_redacted_and_flagged(self):
        det = _make_detector(NoopClient())
        spans = det.detect("ABN: 12 345 678 901")
        assert any(s.needs_review and s.validator_passed is False for s in spans)
        # The full malformed value must be covered by detection spans (no residue).
        assert any(s.end - s.start >= len("12 345 678 901") for s in spans)

    def test_valid_tfn_kept_without_review_flag(self):
        det = _make_detector(NoopClient())
        spans = det.detect("TFN 123 456 782")
        tfn = [s for s in spans if s.category == PIICategory.TFN]
        assert tfn
        assert all(not s.needs_review for s in tfn)


# ---------------------------------------------------------------------------
# Deduplication: same span found by regex AND LLM → one result
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_no_duplicate_tfn_with_mock_client(self):
        from pii_redactor.llm_client import MockClient

        det = _make_detector(MockClient())
        spans = det.detect("TFN: 123 456 782")
        tfn_spans = [s for s in spans if s.category == PIICategory.TFN]
        assert len(tfn_spans) == 1

    def test_no_duplicate_abn_with_mock_client(self):
        from pii_redactor.llm_client import MockClient

        det = _make_detector(MockClient())
        spans = det.detect("ABN 33 051 775 556")
        abn_spans = [s for s in spans if s.category == PIICategory.ABN]
        assert len(abn_spans) == 1


# ---------------------------------------------------------------------------
# LLM-detected spans (names, addresses) complement regex spans
# ---------------------------------------------------------------------------

class TestHybridCombination:
    def test_regex_catches_tfn_llm_catches_name(self):
        det = _make_detector(NameDetectingClient())
        text = "Client John Smith has TFN 123 456 782"
        spans = det.detect(text)
        cats = {s.category for s in spans}
        assert PIICategory.TFN in cats
        assert PIICategory.NAME in cats

    def test_name_only_in_llm_path(self):
        # With prepass disabled, NameDetectingClient still catches name
        det = _make_detector(NameDetectingClient(), use_regex_prepass=False)
        spans = det.detect("Client Jane Doe called today")
        assert any(s.category == PIICategory.NAME for s in spans)


# ---------------------------------------------------------------------------
# _regex_detect unit tests
# ---------------------------------------------------------------------------

class TestRegexDetectMethod:
    def test_returns_pii_spans(self):
        det = _make_detector(NoopClient())
        spans = det._regex_detect("TFN: 123 456 782, Email: a@b.com")
        assert all(isinstance(s, PIISpan) for s in spans)

    def test_span_positions_correct(self):
        text = "TFN: 123 456 782"
        det = _make_detector(NoopClient())
        spans = det._regex_detect(text)
        tfn = next(s for s in spans if s.category == PIICategory.TFN)
        assert text[tfn.start : tfn.end] == tfn.value
