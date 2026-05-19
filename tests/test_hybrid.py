"""Tests for the hybrid OpenAI + AU validator pipeline.

These exercise the resolver and regex-supplement layers without requiring
transformers/torch (the GPU layer is exercised separately at bench time).

A FakeOpenAIBackend feeds known spans through the orchestrator so the
merge / resolution behaviour is fully unit-testable on CPU.
"""
from __future__ import annotations

from pathlib import Path

from pii_redactor import AuditLog, PIICategory, Pipeline, Redactor
from pii_redactor.hybrid import HybridDetector
from pii_redactor.hybrid.au_resolver import resolve_account_numbers, resolve_one
from pii_redactor.hybrid.regex_supplement import supplement_with_regex


class FakeOpenAIBackend:
    """Stand-in for OpenAIPrivacyFilter — returns canned predictions."""

    name = "fake-openai"

    def __init__(self, canned: list[tuple[str, int, int, str]]):
        self._canned = canned

    def predict(self, text):  # noqa: ARG002
        return list(self._canned)

    def warmup(self):
        pass


# --- au_resolver -------------------------------------------------------------

def test_resolve_one_picks_tfn_via_checksum():
    cat, passed = resolve_one("123 456 782")
    assert cat == PIICategory.TFN
    assert passed is True


def test_resolve_one_picks_abn_via_checksum():
    cat, passed = resolve_one("33 051 775 556")
    assert cat == PIICategory.ABN
    assert passed is True


def test_resolve_one_picks_acn_via_checksum():
    cat, passed = resolve_one("004 085 616")
    assert cat == PIICategory.ACN
    assert passed is True


def test_resolve_one_picks_medicare_via_checksum():
    # Valid Medicare number per the standard ATO checksum
    cat, passed = resolve_one("2123 45670 1")
    assert cat == PIICategory.MEDICARE
    assert passed is True


def test_resolve_one_label_prior_overrides_checksum():
    # Even if checksums fail, an "MRN:" label forces MEDICAL_RECORD_NUMBER
    text = "Patient details — MRN: 12345"
    start = text.index("12345")
    cat, _ = resolve_one(
        "12345",
        source_text=text,
        span_start=start,
        span_end=start + 5,
    )
    assert cat == PIICategory.MEDICAL_RECORD_NUMBER


def test_resolve_one_mrn_label_prior_across_dash():
    """Phase 2.x widening: MRN-A123456 — label binding survives a `-`."""
    text = "Patient MRN-A123456 admitted yesterday."
    start = text.index("A123456")
    cat, _ = resolve_one(
        "A123456",
        source_text=text,
        span_start=start,
        span_end=start + len("A123456"),
        openai_category="account_number",
    )
    assert cat == PIICategory.MEDICAL_RECORD_NUMBER


def test_resolve_one_mrn_label_prior_across_colon_space():
    """Phase 2.x widening: 'MRN: 123456' — label binding survives ': '."""
    text = "Medical record MRN: 686040. Admitting clinician."
    start = text.index("686040")
    cat, _ = resolve_one(
        "686040",
        source_text=text,
        span_start=start,
        span_end=start + 6,
        openai_category="account_number",
    )
    assert cat == PIICategory.MEDICAL_RECORD_NUMBER


def test_resolve_one_non_mrn_digit_run_does_not_steal_mrn_label():
    """A 4-digit-run with a TFN label nearby still binds to TFN, not MRN.
    The MRN widening must not corrupt other label bindings.
    """
    text = "Customer TFN: 999999999. (no MRN context)."
    start = text.index("999999999")
    cat, _ = resolve_one(
        "999999999",
        source_text=text,
        span_start=start,
        span_end=start + 9,
        openai_category="account_number",
    )
    assert cat == PIICategory.TFN


def test_resolve_one_label_prior_tfn_with_bad_checksum():
    # "TFN: 999999999" — label says TFN, checksum fails. We keep TFN
    # category but flag validator_passed=False so the policy layer can
    # decide whether to redact regardless.
    text = "TFN: 999999999"
    start = text.index("999")
    cat, passed = resolve_one(
        "999999999",
        source_text=text,
        span_start=start,
        span_end=start + 9,
    )
    assert cat == PIICategory.TFN
    assert passed is False


def test_resolve_one_ihi_structural():
    cat, passed = resolve_one("8003 6080 0029 0436")
    assert cat == PIICategory.HEALTHCARE_IDENTIFIER
    assert passed is None


def test_resolve_one_passport_structural():
    cat, _ = resolve_one("PA1234567")
    assert cat == PIICategory.PASSPORT


def test_resolve_one_crn_structural():
    cat, _ = resolve_one("123456789A")
    assert cat == PIICategory.CRN


def test_resolve_one_falls_back_to_generic():
    cat, passed = resolve_one("XYZ123456789ABCDE")
    assert cat == PIICategory.GENERIC_ID
    assert passed is None


def test_resolve_one_secret_returns_username_when_handle_shaped():
    cat, _ = resolve_one("tw_brian740", openai_category="secret")
    assert cat == PIICategory.USERNAME


def test_resolve_account_numbers_batch():
    text = "TFN 123 456 782, ABN 33 051 775 556, random ID XYZ-9999"
    candidates = [
        ("account_number", 4, 15, "123 456 782"),
        ("account_number", 21, 35, "33 051 775 556"),
        ("account_number", 47, 55, "XYZ-9999"),
        ("private_person", 0, 3, "TFN"),  # not an account_number; should pass through
    ]
    spans = resolve_account_numbers(candidates, text)
    cats = [s.category for s in spans]
    assert PIICategory.TFN in cats
    assert PIICategory.ABN in cats
    # XYZ-9999 has no checksum match — falls back to GENERIC_ID
    assert PIICategory.GENERIC_ID in cats
    # private_person is mapped to NAME
    assert PIICategory.NAME in cats


# --- regex_supplement --------------------------------------------------------

def test_supplement_catches_username_openai_missed():
    text = "Account contact: tw_brian740 for billing."
    existing = []  # openai missed it entirely
    extra = supplement_with_regex(text, existing)
    cats = [s.category for s in extra]
    assert PIICategory.USERNAME in cats


def test_supplement_does_not_duplicate_existing_span():
    from pii_redactor.models import PIISpan

    text = "Username: tw_brian740 contact info"
    existing = [
        PIISpan(
            category=PIICategory.USERNAME,
            start=text.index("tw_brian740"),
            end=text.index("tw_brian740") + len("tw_brian740"),
            value="tw_brian740",
        )
    ]
    extra = supplement_with_regex(text, existing)
    # No duplicate username extracted because it overlaps the existing span
    assert all(s.category != PIICategory.USERNAME for s in extra) or all(
        not (s.start == existing[0].start and s.end == existing[0].end) for s in extra
    )


def test_supplement_catches_au_phone_with_extension():
    text = "Call +1-869-341-9301x7005 for service."
    extra = supplement_with_regex(text, [])
    cats = [s.category for s in extra]
    assert PIICategory.PHONE in cats


# --- HybridDetector end-to-end (synchronous, no GPU) ------------------------

def test_hybrid_detector_resolves_tfn_from_openai_account_number():
    text = "Customer TFN: 123 456 782."
    start = text.index("123 456 782")
    end = start + len("123 456 782")
    backend = FakeOpenAIBackend(canned=[("account_number", start, end, "123 456 782")])
    detector = HybridDetector(openai_backend=backend)
    spans = detector.detect(text)
    cats = [s.category for s in spans]
    assert PIICategory.TFN in cats


def test_hybrid_detector_pipeline_redacts_text(tmp_path: Path):
    text = "Customer TFN: 123 456 782. Contact tw_brian740 at +61 2 6271 7000."
    tfn_start = text.index("123 456 782")
    tfn_end = tfn_start + len("123 456 782")
    backend = FakeOpenAIBackend(canned=[
        ("account_number", tfn_start, tfn_end, "123 456 782"),
    ])
    detector = HybridDetector(openai_backend=backend)
    pipeline = Pipeline(
        detector=detector,  # type: ignore[arg-type]
        redactor=Redactor(style="numbered"),
        audit=AuditLog(path=str(tmp_path / "audit.jsonl"), enabled=False),
        model_name="hybrid-test",
    )
    result = pipeline.process_document(text)
    cats = {s.category.value for s in result.spans}
    assert "tfn" in cats
    # Username caught by regex supplement
    assert "username" in cats
    # AU phone caught by regex supplement (OpenAI's fake didn't return it)
    assert "phone" in cats
    # TFN value never appears in redacted text
    assert "123 456 782" not in result.redacted_text


def test_hybrid_detector_invalid_tfn_label_keeps_tfn_category_marks_invalid():
    text = "TFN: 999999999"
    start = text.index("999999999")
    end = start + 9
    backend = FakeOpenAIBackend(canned=[("account_number", start, end, "999999999")])
    detector = HybridDetector(openai_backend=backend, use_regex_supplement=False)
    spans = detector.detect(text)
    tfn_spans = [s for s in spans if s.category == PIICategory.TFN]
    assert len(tfn_spans) == 1
    assert tfn_spans[0].validator_passed is False


def test_hybrid_detector_handles_empty_text():
    backend = FakeOpenAIBackend(canned=[])
    detector = HybridDetector(openai_backend=backend)
    assert detector.detect("") == []


def test_openai_backend_honours_score_threshold(monkeypatch):
    """Phase 2.x: PIIR_HF_SCORE_THRESHOLD env should be honoured by predict()."""
    from pii_redactor.hybrid.openai_backend import OpenAIPrivacyFilter

    # Don't actually load the model — substitute a fake pipeline.
    class _FakePipe:
        def __call__(self, text):  # noqa: ARG002
            return [
                {"entity_group": "private_person", "score": 0.95,
                 "start": 0, "end": 4, "word": "Jane"},
                {"entity_group": "private_address", "score": 0.05,
                 "start": 5, "end": 9, "word": "Doe."},
            ]

    monkeypatch.setenv("PIIR_HF_SCORE_THRESHOLD", "0.5")
    backend = OpenAIPrivacyFilter()
    backend._pipeline = _FakePipe()  # bypass _ensure_loaded()
    backend._device = -1
    out = backend.predict("Jane Doe.")
    assert len(out) == 1
    assert out[0][0] == "private_person"


def test_openai_backend_default_threshold_keeps_all(monkeypatch):
    """Default score_threshold=0.0 → no spans dropped."""
    from pii_redactor.hybrid.openai_backend import OpenAIPrivacyFilter

    class _FakePipe:
        def __call__(self, text):  # noqa: ARG002
            return [
                {"entity_group": "private_person", "score": 0.95,
                 "start": 0, "end": 4, "word": "Jane"},
                {"entity_group": "private_address", "score": 0.05,
                 "start": 5, "end": 9, "word": "Doe."},
            ]

    monkeypatch.delenv("PIIR_HF_SCORE_THRESHOLD", raising=False)
    backend = OpenAIPrivacyFilter()
    backend._pipeline = _FakePipe()
    backend._device = -1
    out = backend.predict("Jane Doe.")
    assert len(out) == 2


def test_build_pipeline_transformers_au_dispatches_to_hybrid(monkeypatch):
    """build_pipeline routes PIIR_BACKEND=transformers_au to the hybrid path."""
    import pii_redactor.hybrid as hybrid_mod

    monkeypatch.setenv("PIIR_BACKEND", "transformers_au")
    called = {}

    def fake_build(cfg, **kw):  # noqa: ARG001
        called["yes"] = True
        return "PIPELINE_STUB"

    monkeypatch.setattr(hybrid_mod, "build_hybrid_pipeline", fake_build)
    # Also patch the symbol the dispatcher imports
    import pii_redactor.pipeline as pipeline_mod

    # The pipeline dispatcher does a local import inside build_pipeline. Patch
    # the module-level binding in pii_redactor.hybrid since that's where the
    # local import resolves.
    from pii_redactor.config import Config

    cfg = Config.from_env()
    assert cfg.backend == "transformers_au"

    # Reimport after monkey-patch to get the patched fn
    result = pipeline_mod.build_pipeline(cfg)
    assert called.get("yes") is True
    assert result == "PIPELINE_STUB"
