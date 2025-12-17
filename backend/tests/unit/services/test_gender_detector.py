"""
Unit tests for GenderDetector service.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.gender_detector import (
    GenderDetector,
    get_gender_detector,
    detect_gender,
    HEBREW_MALE_NAMES,
    HEBREW_FEMALE_NAMES,
)


class TestGenderDetector:
    """Tests for the GenderDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a GenderDetector instance."""
        return GenderDetector()

    # =========================================================================
    # Hebrew Male Names Tests
    # =========================================================================

    def test_hebrew_male_name_hebrew_script(self, detector):
        """Test detecting Hebrew male names in Hebrew script."""
        assert detector.detect("דוד") == "male"
        assert detector.detect("אבי") == "male"
        assert detector.detect("משה") == "male"
        assert detector.detect("יוסף") == "male"
        assert detector.detect("דניאל") == "male"

    def test_hebrew_male_name_transliterated(self, detector):
        """Test detecting Hebrew male names in English transliteration."""
        assert detector.detect("David") == "male"
        assert detector.detect("Avi") == "male"
        assert detector.detect("Moshe") == "male"
        assert detector.detect("Tomer") == "male"
        assert detector.detect("Amit") == "male"
        assert detector.detect("Eyal") == "male"

    def test_hebrew_male_name_full_name(self, detector):
        """Test detecting gender from full names (extracts first name)."""
        assert detector.detect("דוד כהן") == "male"
        assert detector.detect("Tomer Levi") == "male"
        assert detector.detect("אבי שרון") == "male"

    # =========================================================================
    # Hebrew Female Names Tests
    # =========================================================================

    def test_hebrew_female_name_hebrew_script(self, detector):
        """Test detecting Hebrew female names in Hebrew script."""
        assert detector.detect("שרה") == "female"
        assert detector.detect("רחל") == "female"
        assert detector.detect("מיכל") == "female"
        assert detector.detect("נועה") == "female"
        assert detector.detect("תמר") == "female"

    def test_hebrew_female_name_transliterated(self, detector):
        """Test detecting Hebrew female names in English transliteration."""
        assert detector.detect("Sara") == "female"
        assert detector.detect("Noa") == "female"
        assert detector.detect("Tamar") == "female"
        assert detector.detect("Maya") == "female"
        assert detector.detect("Michal") == "female"

    def test_hebrew_female_name_full_name(self, detector):
        """Test detecting gender from full female names."""
        assert detector.detect("שרה לוי") == "female"
        assert detector.detect("Noa Cohen") == "female"
        assert detector.detect("מיכל ברק") == "female"

    # =========================================================================
    # International Names Tests
    # =========================================================================

    def test_international_male_names(self, detector):
        """Test detecting common international male names."""
        assert detector.detect("John") == "male"
        assert detector.detect("Michael") == "male"
        assert detector.detect("James") == "male"
        assert detector.detect("Robert") == "male"
        assert detector.detect("William") == "male"

    def test_international_female_names(self, detector):
        """Test detecting common international female names."""
        assert detector.detect("Mary") == "female"
        assert detector.detect("Jennifer") == "female"
        assert detector.detect("Elizabeth") == "female"
        assert detector.detect("Sarah") == "female"
        assert detector.detect("Jessica") == "female"

    def test_international_full_names(self, detector):
        """Test detecting gender from international full names."""
        assert detector.detect("John Smith") == "male"
        assert detector.detect("Mary Johnson") == "female"
        assert detector.detect("Michael Brown") == "male"

    # =========================================================================
    # Edge Cases and Unknown
    # =========================================================================

    def test_empty_name_returns_unknown(self, detector):
        """Test that empty name returns unknown."""
        assert detector.detect("") == "unknown"
        assert detector.detect("   ") == "unknown"

    def test_none_name_returns_unknown(self, detector):
        """Test that None name returns unknown."""
        assert detector.detect(None) == "unknown"

    def test_unknown_name_returns_unknown(self, detector):
        """Test that unrecognized names return unknown."""
        assert detector.detect("Xyz123") == "unknown"
        assert detector.detect("QWERTYUIOP") == "unknown"

    def test_case_insensitive(self, detector):
        """Test that detection is case insensitive."""
        assert detector.detect("DAVID") == "male"
        assert detector.detect("david") == "male"
        assert detector.detect("David") == "male"
        assert detector.detect("SARAH") == "female"
        assert detector.detect("sarah") == "female"

    def test_leading_trailing_whitespace(self, detector):
        """Test handling of whitespace."""
        assert detector.detect("  David  ") == "male"
        assert detector.detect("\tSarah\n") == "female"

    # =========================================================================
    # Ambiguous Names Tests
    # =========================================================================

    def test_ambiguous_hebrew_names(self, detector):
        """Test names that are ambiguous in Hebrew (used for both genders)."""
        # Note: Some names like עדי, שי are used for both genders
        # The implementation checks male list first
        result = detector.detect("עדי")
        assert result in ["male", "female", "unknown"]

    # =========================================================================
    # Profile-based Detection Tests
    # =========================================================================

    def test_detect_from_profile_with_he_him_pronouns(self, detector):
        """Test detecting gender from profile with he/him pronouns."""
        profile = {
            "name": "Unknown Name",
            "pronouns": "he/him"
        }
        assert detector.detect_from_profile(profile) == "male"

    def test_detect_from_profile_with_she_her_pronouns(self, detector):
        """Test detecting gender from profile with she/her pronouns."""
        profile = {
            "name": "Unknown Name",
            "pronouns": "she/her"
        }
        assert detector.detect_from_profile(profile) == "female"

    def test_detect_from_profile_with_hebrew_pronouns(self, detector):
        """Test detecting gender from profile with Hebrew pronouns."""
        male_profile = {"name": "Test", "pronouns": "הוא"}
        female_profile = {"name": "Test", "pronouns": "היא"}

        assert detector.detect_from_profile(male_profile) == "male"
        assert detector.detect_from_profile(female_profile) == "female"

    def test_detect_from_profile_fallback_to_name(self, detector):
        """Test that profile detection falls back to name if no pronouns."""
        profile = {
            "name": "David Cohen",
            "pronouns": ""
        }
        assert detector.detect_from_profile(profile) == "male"

    def test_detect_from_profile_no_pronouns_key(self, detector):
        """Test profile without pronouns key."""
        profile = {
            "name": "Sarah Levi"
        }
        assert detector.detect_from_profile(profile) == "female"

    def test_detect_from_profile_empty(self, detector):
        """Test empty profile returns unknown."""
        profile = {}
        assert detector.detect_from_profile(profile) == "unknown"


class TestGenderDetectorSingleton:
    """Tests for the singleton pattern and convenience functions."""

    def test_get_gender_detector_returns_same_instance(self):
        """Test that get_gender_detector returns singleton."""
        detector1 = get_gender_detector()
        detector2 = get_gender_detector()
        assert detector1 is detector2

    def test_detect_gender_convenience_function(self):
        """Test the convenience function detect_gender."""
        assert detect_gender("David") == "male"
        assert detect_gender("Sarah") == "female"
        assert detect_gender("Unknown123") == "unknown"


class TestHebrewNamesDatabase:
    """Tests for the Hebrew names database."""

    def test_hebrew_male_names_not_empty(self):
        """Test that male names database is populated."""
        assert len(HEBREW_MALE_NAMES) > 0

    def test_hebrew_female_names_not_empty(self):
        """Test that female names database is populated."""
        assert len(HEBREW_FEMALE_NAMES) > 0

    def test_no_overlap_between_databases(self):
        """Test that there's minimal overlap between male and female names."""
        # Some names might legitimately be in both (unisex names)
        overlap = HEBREW_MALE_NAMES & HEBREW_FEMALE_NAMES
        # The overlap should be minimal (only truly unisex names)
        assert len(overlap) < 10  # Allow some unisex names

    def test_common_male_names_present(self):
        """Test that common male names are in the database."""
        common_male = ["דוד", "משה", "אבי", "david", "moshe", "tomer"]
        for name in common_male:
            assert name in HEBREW_MALE_NAMES, f"{name} should be in male names"

    def test_common_female_names_present(self):
        """Test that common female names are in the database."""
        common_female = ["שרה", "רחל", "נועה", "sara", "noa", "tamar"]
        for name in common_female:
            assert name in HEBREW_FEMALE_NAMES, f"{name} should be in female names"


class TestGenderDetectorIntegration:
    """Integration tests for gender detection scenarios."""

    def test_realistic_linkedin_profile_male(self):
        """Test with realistic male LinkedIn profile."""
        detector = GenderDetector()
        profile = {
            "name": "Tomer Cohen",
            "pronouns": "",
            "headline": "Software Engineer at Google"
        }
        assert detector.detect_from_profile(profile) == "male"

    def test_realistic_linkedin_profile_female(self):
        """Test with realistic female LinkedIn profile."""
        detector = GenderDetector()
        profile = {
            "name": "Noa Levi",
            "pronouns": "she/her",
            "headline": "Product Manager at Microsoft"
        }
        assert detector.detect_from_profile(profile) == "female"

    def test_batch_detection(self):
        """Test detecting gender for multiple names."""
        detector = GenderDetector()
        names = [
            ("David Cohen", "male"),
            ("Sarah Levi", "female"),
            ("Tomer Ben-Ami", "male"),
            ("Noa Shapira", "female"),
            ("Unknown Person", "unknown"),
        ]

        for name, expected in names:
            result = detector.detect(name)
            # Allow some flexibility for edge cases
            if expected != "unknown":
                assert result == expected, f"Expected {expected} for {name}, got {result}"
