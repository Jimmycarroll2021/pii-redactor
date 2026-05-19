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
    detector = HybridDetector(openai_backend=backend, use_llama_pass=False)
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
    detector = HybridDetector(openai_backend=backend, use_llama_pass=False)
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
    detector = HybridDetector(
        openai_backend=backend,
        use_regex_supplement=False,
        use_llama_pass=False,
    )
    spans = detector.detect(text)
    tfn_spans = [s for s in spans if s.category == PIICategory.TFN]
    assert len(tfn_spans) == 1
    assert tfn_spans[0].validator_passed is False


def test_hybrid_detector_handles_empty_text():
    backend = FakeOpenAIBackend(canned=[])
    detector = HybridDetector(openai_backend=backend, use_llama_pass=False)
    assert detector.detect("") == []


def test_regex_supplement_skips_username_when_env_disables(monkeypatch):
    """Phase 2.x: PIIR_REGEX_USERNAME=false → no USERNAME from regex layer."""
    monkeypatch.setenv("PIIR_REGEX_USERNAME", "false")
    text = "Contact: tw_brian740 for billing."
    extra = supplement_with_regex(text, [])
    assert all(s.category != PIICategory.USERNAME for s in extra)


def test_regex_supplement_default_keeps_username():
    """Default behaviour (no env) keeps USERNAME hits intact."""
    text = "Contact: tw_brian740 for billing."
    extra = supplement_with_regex(text, [])
    assert any(s.category == PIICategory.USERNAME for s in extra)


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


class _FakeLlamaPass:
    """Stand-in for LlamaNERPass that returns canned predictions."""

    def __init__(self, canned: list[tuple[str, int, int, str]]):
        self._canned = canned
        self.name = "fake-llama"

    def predict(self, text):  # noqa: ARG002
        return list(self._canned)

    def warmup(self):
        pass


def test_hybrid_detector_unions_openai_and_llama_spans():
    """Phase 2.x: llama pass recovers PII OpenAI's calibrated head missed."""
    text = "Patient Daniel Lee, DOB 18/03/1986. MRN-686040."
    openai_canned = [
        # OpenAI catches the date but misses the name (calibrated head fault)
        ("private_date", text.index("18/03/1986"), text.index("18/03/1986") + 10, "18/03/1986"),
    ]
    llama_canned = [
        # llama catches the name + the MRN with full label
        ("private_person", text.index("Daniel Lee"), text.index("Daniel Lee") + 10, "Daniel Lee"),
        ("account_number", text.index("MRN-686040"), text.index("MRN-686040") + 10, "MRN-686040"),
    ]
    openai_backend = FakeOpenAIBackend(canned=openai_canned)
    llama_backend = _FakeLlamaPass(canned=llama_canned)
    detector = HybridDetector(
        openai_backend=openai_backend,
        llama_pass=llama_backend,
        use_llama_pass=True,
        use_regex_supplement=False,
    )
    spans = detector.detect(text)
    cats = {s.category.value for s in spans}
    assert "name" in cats
    assert "date_of_birth" in cats or "date" in cats
    assert "medical_record_number" in cats


def test_hybrid_detector_llama_disabled_falls_back_to_openai_only():
    """use_llama_pass=False reproduces v0.2.0 behaviour."""
    text = "Daniel Lee."
    openai_canned = [
        ("private_person", 0, 10, "Daniel Lee"),
    ]
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=openai_canned),
        use_llama_pass=False,
        use_regex_supplement=False,
    )
    spans = detector.detect(text)
    assert len(spans) == 1
    assert spans[0].category == PIICategory.NAME


def test_hybrid_detector_name_includes_both_backends():
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=[]),
        llama_pass=_FakeLlamaPass(canned=[]),
        use_llama_pass=True,
    )
    assert "fake-llama" in detector.name


def test_llama_pass_disabled_returns_empty(monkeypatch):
    """PIIR_LLAMA_ENABLED=false → no calls, empty list."""
    from pii_redactor.hybrid.llama_pass import LlamaNERPass

    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "false")
    pass_ = LlamaNERPass()
    assert pass_.predict("Some text with Daniel Lee.") == []


def test_llama_pass_skips_oversized_doc(monkeypatch):
    """Documents larger than PIIR_LLAMA_MAX_CHARS are skipped (latency budget)."""
    from pii_redactor.hybrid.llama_pass import LlamaNERPass

    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    pass_ = LlamaNERPass(max_chars=100)
    huge = "x" * 5000
    assert pass_.predict(huge) == []


def test_llama_pass_soft_fails_on_client_error(monkeypatch):
    """A throwing OllamaClient must not surface — return [] instead."""
    from pii_redactor.hybrid.llama_pass import LlamaNERPass

    monkeypatch.delenv("PIIR_LLAMA_ENABLED", raising=False)
    pass_ = LlamaNERPass(base_url="http://127.0.0.1:1")  # unreachable
    pass_._ensure_loaded()

    class _Boom:
        def complete(self, **kw):  # noqa: ARG002
            raise RuntimeError("connection refused")

    pass_._client = _Boom()
    assert pass_.predict("Daniel Lee.") == []


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


# --- Phase 2.y llama-gate regressions ---------------------------------------


def test_gate_mode_never_skips_llama_even_with_narrative():
    """PIIR_LLAMA_GATE=never reproduces v0.2.0 behaviour (openai+regex only)."""
    from pii_redactor.hybrid import should_invoke_llama

    invoke, reason = should_invoke_llama(
        "The patient Daniel Lee presented with severe symptoms after admission",
        openai_scores=[0.5],
        mode="never",
    )
    assert invoke is False
    assert "never" in reason


def test_gate_mode_always_invokes_llama_even_on_short_doc():
    """PIIR_LLAMA_GATE=always reproduces v0.3.0 behaviour."""
    from pii_redactor.hybrid import should_invoke_llama

    invoke, reason = should_invoke_llama(
        "x", openai_scores=[0.99], mode="always"
    )
    assert invoke is True
    assert "always" in reason


def test_gate_confidence_skips_short_structured_doc():
    """Short doc, high openai score, no cue → gate skips llama."""
    from pii_redactor.hybrid import should_invoke_llama

    text = "TFN: 123 456 782."  # 4 tokens, no cue
    invoke, reason = should_invoke_llama(
        text, openai_scores=[0.99], mode="confidence",
        min_score=0.85, min_tokens=50,
    )
    assert invoke is False
    assert "skip" in reason


def test_gate_confidence_invokes_on_multi_low_openai_scores():
    """Two or more hedging openai spans flip the gate to invoke.

    A single low-confidence span is normal noise; two or more is a
    systematic signal that the calibrated head is under-recalling and
    the prompt-driven llama pass should run.
    """
    from pii_redactor.hybrid import should_invoke_llama

    invoke, reason = should_invoke_llama(
        "A short doc", openai_scores=[0.7, 0.5, 0.99], mode="confidence",
        min_score=0.85, min_tokens=200,
    )
    assert invoke is True
    assert "openai_low_conf" in reason


def test_gate_confidence_skips_single_low_score_span():
    """One low-confidence span alone does NOT invoke — that's noise."""
    from pii_redactor.hybrid import should_invoke_llama

    invoke, reason = should_invoke_llama(
        "A short doc with one span", openai_scores=[0.7, 0.99, 0.99],
        mode="confidence", min_score=0.85, min_tokens=200,
    )
    assert invoke is False
    assert "skip" in reason


def test_gate_confidence_invokes_on_narrative_cue():
    """Clinical / legal narrative cues flip the gate to invoke even on a
    short document with no openai spans yet emitted."""
    from pii_redactor.hybrid import should_invoke_llama

    text = "The patient was admitted to ward 3."
    invoke, reason = should_invoke_llama(
        text, openai_scores=[], mode="confidence",
        min_score=0.85, min_tokens=50,
    )
    assert invoke is True
    assert reason == "narrative_cue"


def test_gate_confidence_invokes_on_long_doc():
    """Long doc (>= MIN_TOKENS) flips the gate to invoke even with no cue."""
    from pii_redactor.hybrid import should_invoke_llama

    text = "word " * 60  # 60 tokens, no narrative cue
    invoke, reason = should_invoke_llama(
        text, openai_scores=[0.99], mode="confidence",
        min_score=0.85, min_tokens=50,
    )
    assert invoke is True
    assert "tokens=" in reason


def test_gate_confidence_invokes_on_mrn_label():
    """MRN-XXX style labels trigger the gate (medical narrative cue)."""
    from pii_redactor.hybrid import should_invoke_llama

    invoke, reason = should_invoke_llama(
        "MRN-686040 Daniel Lee.",
        openai_scores=[0.99], mode="confidence",
        min_score=0.85, min_tokens=50,
    )
    assert invoke is True
    assert reason == "narrative_cue"


def test_gate_unknown_mode_falls_back_to_confidence(monkeypatch):
    """Unknown env value coerces to default (confidence)."""
    monkeypatch.setenv("PIIR_LLAMA_GATE", "garbage")
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=[]),
        llama_pass=_FakeLlamaPass(canned=[]),
        use_llama_pass=True,
    )
    assert detector.gate_mode == "confidence"


def test_gate_env_knobs_picked_up(monkeypatch):
    """Env knobs surface on the HybridDetector instance."""
    monkeypatch.setenv("PIIR_LLAMA_GATE", "always")
    monkeypatch.setenv("PIIR_LLAMA_GATE_MIN_SCORE", "0.91")
    monkeypatch.setenv("PIIR_LLAMA_GATE_MIN_TOKENS", "73")
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=[]),
        llama_pass=_FakeLlamaPass(canned=[]),
        use_llama_pass=True,
    )
    assert detector.gate_mode == "always"
    assert detector.gate_min_score == 0.91
    assert detector.gate_min_tokens == 73


def test_hybrid_detector_gate_skips_llama_call_on_easy_doc():
    """End-to-end: short structured doc, high openai score → llama
    .predict() is NEVER called (the gate skips it). This is the
    throughput-recovery property that takes Gretel 0.34 d/s → 3+ d/s.
    """
    text = "Customer TFN: 123 456 782."
    start = text.index("123 456 782")
    end = start + len("123 456 782")
    backend = FakeOpenAIBackend(
        canned=[("account_number", start, end, "123 456 782")]
    )

    class _SpyLlama:
        name = "spy-llama"

        def __init__(self):
            self.called = 0

        def predict(self, text):  # noqa: ARG002
            self.called += 1
            return []

        def warmup(self):
            pass

    spy = _SpyLlama()
    detector = HybridDetector(
        openai_backend=backend,
        llama_pass=spy,
        use_llama_pass=True,
        gate_mode="confidence",
        gate_min_score=0.85,
        gate_min_tokens=50,
    )
    spans = detector.detect(text)
    assert spy.called == 0
    # The TFN still gets resolved from the openai span
    assert any(s.category == PIICategory.TFN for s in spans)
    # gate_stats reflects the skip
    stats = detector.gate_stats()
    assert stats["llama_skips"] == 1
    assert stats["llama_invocations"] == 0


def test_hybrid_detector_gate_invokes_llama_on_narrative_doc():
    """End-to-end: clinical narrative cue → gate invokes llama, union
    behaviour matches v0.3.0 (name recovered)."""
    text = "Patient Daniel Lee, DOB 18/03/1986. MRN-686040."
    openai_canned = [
        ("private_date", text.index("18/03/1986"),
         text.index("18/03/1986") + 10, "18/03/1986"),
    ]
    llama_canned = [
        ("private_person", text.index("Daniel Lee"),
         text.index("Daniel Lee") + 10, "Daniel Lee"),
    ]
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=openai_canned),
        llama_pass=_FakeLlamaPass(canned=llama_canned),
        use_llama_pass=True,
        gate_mode="confidence",
        gate_min_score=0.85,
        gate_min_tokens=50,
    )
    spans = detector.detect(text)
    cats = {s.category.value for s in spans}
    assert "name" in cats
    stats = detector.gate_stats()
    assert stats["llama_invocations"] == 1
    assert stats["llama_skips"] == 0


def test_hybrid_detector_gate_always_matches_v030_behaviour():
    """gate=always reproduces v0.3.0 (no gate) regardless of doc shape."""
    text = "Alex Wong."  # short, no cue, high score — gate would normally skip
    openai_canned = []
    llama_canned = [
        ("private_person", 0, 9, "Alex Wong"),
    ]
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=openai_canned),
        llama_pass=_FakeLlamaPass(canned=llama_canned),
        use_llama_pass=True,
        gate_mode="always",
        use_regex_supplement=False,
    )
    spans = detector.detect(text)
    # gate=always means llama runs even though doc is short/structured
    assert any(s.category == PIICategory.NAME for s in spans)


def test_hybrid_detector_gate_never_matches_v020_behaviour():
    """gate=never reproduces v0.2.0 (openai+regex only)."""
    text = "Patient Daniel Lee presented for follow-up."
    llama_canned = [
        ("private_person", text.index("Daniel Lee"),
         text.index("Daniel Lee") + 10, "Daniel Lee"),
    ]
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=[]),
        llama_pass=_FakeLlamaPass(canned=llama_canned),
        use_llama_pass=True,
        gate_mode="never",
    )
    spans = detector.detect(text)
    # llama would have added the name, but the gate blocked it
    assert all(s.category != PIICategory.NAME for s in spans)


def test_hybrid_detector_name_shows_gate_mode():
    """The model_used label exposes the gate mode for observability."""
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=[]),
        llama_pass=_FakeLlamaPass(canned=[]),
        use_llama_pass=True,
        gate_mode="confidence",
    )
    assert "gate=confidence" in detector.name


# --- predict_with_scores -----------------------------------------------------


def test_openai_backend_predict_with_scores_returns_score(monkeypatch):
    """predict_with_scores exposes the aggregator score so the gate can read it."""
    from pii_redactor.hybrid.openai_backend import OpenAIPrivacyFilter

    class _FakePipe:
        def __call__(self, text):  # noqa: ARG002
            return [
                {"entity_group": "private_person", "score": 0.95,
                 "start": 0, "end": 4, "word": "Jane"},
                {"entity_group": "private_date", "score": 0.62,
                 "start": 5, "end": 15, "word": "01/01/1990"},
            ]

    monkeypatch.delenv("PIIR_HF_SCORE_THRESHOLD", raising=False)
    backend = OpenAIPrivacyFilter()
    backend._pipeline = _FakePipe()
    backend._device = -1
    out = backend.predict_with_scores("Jane 01/01/1990.")
    assert len(out) == 2
    cats = [t[0] for t in out]
    scores = [t[4] for t in out]
    assert "private_person" in cats
    assert min(scores) < 0.85  # low-confidence date span available to the gate
    assert max(scores) > 0.85


def test_hybrid_detector_uses_predict_with_scores_when_available():
    """HybridDetector prefers the scored API but falls back to predict()."""
    text = "Sample text"

    class _LegacyBackend:
        """Backend that only implements predict() — no scored API."""
        name = "legacy"

        def predict(self, text):  # noqa: ARG002
            return [("private_person", 0, 6, "Sample")]

        def warmup(self):
            pass

    detector = HybridDetector(
        openai_backend=_LegacyBackend(),
        llama_pass=_FakeLlamaPass(canned=[]),
        use_llama_pass=True,
        gate_mode="confidence",
        gate_min_score=0.85,
        gate_min_tokens=50,
    )
    spans = detector.detect(text)
    # Fell back to predict() with score=1.0, then gate evaluated and (no
    # cue, short, high score) → skipped llama. The openai span survived.
    assert any(s.category == PIICategory.NAME for s in spans)


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


# --- Phase 2.z vLLM narrative backend ---------------------------------------


def test_vllm_pass_disabled_returns_empty(monkeypatch):
    """PIIR_LLAMA_ENABLED=false → no calls, empty list."""
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass

    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "false")
    pass_ = VLLMNERPass()
    assert pass_.predict("Some text with Daniel Lee.") == []


def test_vllm_pass_skips_oversized_doc(monkeypatch):
    """Documents larger than PIIR_LLAMA_MAX_CHARS are skipped (latency budget)."""
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass

    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    pass_ = VLLMNERPass(max_chars=100)
    huge = "x" * 5000
    assert pass_.predict(huge) == []


def test_vllm_pass_soft_fails_on_unreachable(monkeypatch):
    """An unreachable vLLM endpoint must not surface — return [] instead."""
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass

    monkeypatch.delenv("PIIR_LLAMA_ENABLED", raising=False)
    pass_ = VLLMNERPass(base_url="http://127.0.0.1:1", timeout_s=0.5)
    assert pass_.predict("Daniel Lee.") == []


def test_vllm_pass_parses_canonical_response(monkeypatch):
    """vLLM call returns OpenAI-shape tuples when given a valid JSON body."""
    import json as _json
    from unittest.mock import MagicMock

    from pii_redactor import llm_client as llm_mod
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass

    monkeypatch.delenv("PIIR_LLAMA_ENABLED", raising=False)

    captured = {}

    def fake_post_with_retry(url, payload, timeout, retries=3):  # noqa: ARG001
        captured["url"] = url
        captured["payload"] = payload
        resp = MagicMock()
        resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": _json.dumps(
                            {"pii": [{"category": "name", "value": "Daniel Lee"}]}
                        ),
                    }
                }
            ]
        }
        return resp

    monkeypatch.setattr(llm_mod, "_post_with_retry", fake_post_with_retry)

    pass_ = VLLMNERPass(
        base_url="http://vllm:11500",
        model="llama3.1-8b-awq",
        timeout_s=5.0,
    )
    out = pass_.predict("Patient Daniel Lee presented.")
    assert any(cat == "private_person" and val == "Daniel Lee" for cat, _, _, val in out)
    assert captured["url"] == "http://vllm:11500/v1/chat/completions"
    assert captured["payload"]["model"] == "llama3.1-8b-awq"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["temperature"] == 0.0


def test_vllm_pass_health_check_ok_and_fail(monkeypatch):
    """health_check() returns True on 200, False on URLError."""
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass

    class _OkCtx:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):  # noqa: D401
            return False

    pass_ = VLLMNERPass(base_url="http://vllm:11500", timeout_s=1.0)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: _OkCtx(),  # noqa: ARG005
    )
    assert pass_.health_check() is True

    def _boom(*a, **kw):  # noqa: ARG001
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert pass_.health_check() is False


def test_select_llama_backend_explicit_ollama(monkeypatch):
    """PIIR_LLAMA_BACKEND=ollama short-circuits the auto-detection."""
    from pii_redactor.hybrid.llama_pass import LlamaNERPass
    from pii_redactor.hybrid.vllm_pass import select_llama_backend

    monkeypatch.setenv("PIIR_LLAMA_BACKEND", "ollama")
    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    name, inst = select_llama_backend()
    assert name == "ollama"
    assert isinstance(inst, LlamaNERPass)


def test_select_llama_backend_explicit_vllm(monkeypatch):
    """PIIR_LLAMA_BACKEND=vllm builds the vLLM pass even if endpoint absent."""
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass, select_llama_backend

    monkeypatch.setenv("PIIR_LLAMA_BACKEND", "vllm")
    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    name, inst = select_llama_backend()
    assert name == "vllm"
    assert isinstance(inst, VLLMNERPass)


def test_select_llama_backend_auto_prefers_vllm(monkeypatch):
    """auto mode picks vLLM when its health check passes."""
    from pii_redactor.hybrid import vllm_pass as vllm_mod
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass, select_llama_backend

    monkeypatch.setenv("PIIR_LLAMA_BACKEND", "auto")
    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    monkeypatch.setattr(vllm_mod.VLLMNERPass, "health_check", lambda self: True)
    name, inst = select_llama_backend()
    assert name == "vllm"
    assert isinstance(inst, VLLMNERPass)


def test_select_llama_backend_auto_falls_back_to_ollama(monkeypatch):
    """auto mode falls back to Ollama when vLLM is unreachable."""
    from pii_redactor.hybrid import vllm_pass as vllm_mod
    from pii_redactor.hybrid.llama_pass import LlamaNERPass
    from pii_redactor.hybrid.vllm_pass import select_llama_backend

    monkeypatch.setenv("PIIR_LLAMA_BACKEND", "auto")
    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    monkeypatch.setattr(vllm_mod.VLLMNERPass, "health_check", lambda self: False)
    name, inst = select_llama_backend()
    assert name == "ollama"
    assert isinstance(inst, LlamaNERPass)


def test_select_llama_backend_disabled(monkeypatch):
    """PIIR_LLAMA_ENABLED=false → disabled sentinel, no instance."""
    from pii_redactor.hybrid.vllm_pass import select_llama_backend

    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "false")
    name, inst = select_llama_backend()
    assert name == "disabled"
    assert inst is None


def test_hybrid_detector_records_vllm_backend_name(monkeypatch):
    """HybridDetector surfaces vLLM backend identity via gate_stats."""
    from pii_redactor.hybrid.pipeline import HybridDetector
    from pii_redactor.hybrid.vllm_pass import VLLMNERPass

    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    fake = VLLMNERPass(base_url="http://vllm:11500", model="llama3.1-8b-awq")
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=[]),
        llama_pass=fake,
        use_llama_pass=True,
        gate_mode="always",
    )
    stats = detector.gate_stats()
    assert stats["llama_backend"] == "vllm"
    assert stats["vllm_model"] == "llama3.1-8b-awq"
    assert stats["vllm_quant"] == "awq_marlin"


def test_hybrid_detector_records_ollama_backend_name(monkeypatch):
    """HybridDetector surfaces Ollama backend identity via gate_stats."""
    from pii_redactor.hybrid.llama_pass import LlamaNERPass
    from pii_redactor.hybrid.pipeline import HybridDetector

    monkeypatch.setenv("PIIR_LLAMA_ENABLED", "true")
    fake = LlamaNERPass(base_url="http://ollama:11434", model="llama3.1:8b")
    detector = HybridDetector(
        openai_backend=FakeOpenAIBackend(canned=[]),
        llama_pass=fake,
        use_llama_pass=True,
        gate_mode="always",
    )
    stats = detector.gate_stats()
    assert stats["llama_backend"] == "ollama"
    assert stats["ollama_model"] == "llama3.1:8b"
