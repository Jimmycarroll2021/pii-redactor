"""Validator tests using published Australian government test values."""
from pii_redactor.models import PIICategory
from pii_redactor.validators import (
    PATTERNS,
    validate_abn,
    validate_acn,
    validate_bsb,
    validate_medicare,
    validate_tfn,
)


class TestTFN:
    def test_valid_9_digit(self):
        # ATO published test TFNs
        assert validate_tfn("123 456 782")
        assert validate_tfn("876 543 210")
        assert validate_tfn("123456782")  # no spaces

    def test_invalid_9_digit(self):
        assert not validate_tfn("999 999 999")
        assert not validate_tfn("000 000 000")
        assert not validate_tfn("123 456 789")  # wrong checksum

    def test_wrong_length(self):
        assert not validate_tfn("123")
        assert not validate_tfn("12345")
        assert not validate_tfn("12345678901234")


class TestABN:
    def test_valid(self):
        # Real Australian ABNs (publicly searchable)
        assert validate_abn("33 051 775 556")  # Telstra
        assert validate_abn("51 824 753 556")  # ATO test value
        assert validate_abn("33051775556")     # no spaces

    def test_invalid(self):
        assert not validate_abn("11 111 111 111")
        assert not validate_abn("12 345 678 901")  # bad checksum

    def test_wrong_length(self):
        assert not validate_abn("123")
        assert not validate_abn("1234567890")  # 10 digits


class TestACN:
    def test_valid(self):
        # Real Australian ACNs
        assert validate_acn("051 775 556")  # Telstra (sub-component of ABN)
        assert validate_acn("004 085 616")
        assert validate_acn("051775556")    # no spaces

    def test_invalid(self):
        assert not validate_acn("123 456 789")
        assert not validate_acn("000 000 001")

    def test_wrong_length(self):
        assert not validate_acn("12345")
        assert not validate_acn("1234567890")  # 10 digits


class TestMedicare:
    def test_valid(self):
        # Synthetic but algorithm-valid Medicare numbers
        # Format: XXXX XXXXX X (10 digits) or XXXX XXXXX X-X (11 digits)
        # Generate one programmatically by computing the check digit:
        # First 8 digits: 29572019
        # Weights: 1,3,7,9,1,3,7,9 → 2*1+9*3+5*7+7*9+2*1+0*3+1*7+9*9
        # = 2 + 27 + 35 + 63 + 2 + 0 + 7 + 81 = 217 → 217 % 10 = 7
        # So check digit is 7. Add issue digit '1': 2957201971
        assert validate_medicare("2957 20197 1")
        assert validate_medicare("2957201971")
        assert validate_medicare("2957 20197 1-1")  # with IRN

    def test_invalid(self):
        assert not validate_medicare("1234 56789 0")  # bad checksum

    def test_wrong_length(self):
        assert not validate_medicare("123 456 789")
        assert not validate_medicare("123456789012345")


class TestBSB:
    def test_valid(self):
        assert validate_bsb("062-000")  # CBA
        assert validate_bsb("062000")
        assert validate_bsb("083 000")  # NAB

    def test_invalid(self):
        assert not validate_bsb("12345")
        assert not validate_bsb("1234567")


class TestPhoneRegex:
    """Regression tests for Bug 1 — phone regex must cover all AU formats."""

    def _find(self, text: str):
        return PATTERNS[PIICategory.PHONE].search(text)

    def test_bracketed_02(self):
        m = self._find("(02) 6271 7000")
        assert m is not None and m.group() == "(02) 6271 7000"

    def test_bracketed_03(self):
        m = self._find("(03) 9123 4567")
        assert m is not None and m.group() == "(03) 9123 4567"

    def test_mobile_04(self):
        m = self._find("0412 345 678")
        assert m is not None and m.group() == "0412 345 678"

    def test_international_plus61(self):
        m = self._find("+61 2 6271 7000")
        assert m is not None

    def test_no_match_inside_abn(self):
        # Bug 3: bare digit run from a bad ABN must not produce a phone span
        assert PATTERNS[PIICategory.PHONE].search("12 345 678 901") is None


class TestBSBRegex:
    """Regression tests for Bug 2 — BSB must not fire inside TFN digit runs."""

    def test_standalone_bsb_matches(self):
        m = PATTERNS[PIICategory.BSB_ACCOUNT].search("BSB: 062-000")
        assert m is not None and m.group() == "062-000"

    def test_no_false_positive_in_compact_tfn(self):
        # No spaces — BSB lookahead can't split the 9-digit run
        assert PATTERNS[PIICategory.BSB_ACCOUNT].search("123456782") is None


class TestNewDocumentPatterns:
    """New regex coverage: driver licence, passport, Centrelink CRN."""

    def test_numeric_driver_licence(self):
        m = PATTERNS[PIICategory.DRIVER_LICENCE].search("licence 12345678")
        assert m is not None and m.group() == "12345678"

    def test_letter_prefix_driver_licence(self):
        m = PATTERNS[PIICategory.DRIVER_LICENCE].search("SA licence C123456")
        assert m is not None and m.group() == "C123456"

    def test_passport_two_letter(self):
        m = PATTERNS[PIICategory.PASSPORT].search("passport PA1234567")
        assert m is not None and m.group() == "PA1234567"

    def test_centrelink_crn(self):
        m = PATTERNS[PIICategory.CRN].search("CRN 555444333A")
        assert m is not None and m.group() == "555444333A"

    def test_patient_id_is_context_bound(self):
        text = "Patient ID: PT-448812"
        m = PATTERNS[PIICategory.PATIENT_ID].search(text)
        assert m is not None
        assert m.group("value") == "PT-448812"

    def test_medical_record_number_is_context_bound(self):
        text = "MRN HOSP-998271"
        m = PATTERNS[PIICategory.MEDICAL_RECORD_NUMBER].search(text)
        assert m is not None
        assert m.group("value") == "HOSP-998271"

    def test_healthcare_identifier_is_context_bound(self):
        text = "IHI 8003 6000 0000 0000"
        m = PATTERNS[PIICategory.HEALTHCARE_IDENTIFIER].search(text)
        assert m is not None
        assert m.group("value") == "8003 6000 0000 0000"
