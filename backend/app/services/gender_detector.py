import gender_guesser.detector as gender_detector

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Hebrew names database (common Israeli names)
HEBREW_MALE_NAMES = {
    # Common male names
    "אבי", "אביב", "אביגדור", "אביעד", "אבירם", "אבישי", "אברהם", "אדם", "אהרון",
    "אורי", "אורן", "אייל", "איתי", "איתן", "אלון", "אלי", "אליהו", "אמיר",
    "ארז", "אריאל", "אריה", "אשר", "בועז", "בני", "בנימין", "גד", "גדעון",
    "גיא", "גיל", "גלעד", "דוד", "דור", "דני", "דניאל", "דן", "הראל",
    "זיו", "חי", "חיים", "יאיר", "יגאל", "יהונתן", "יהודה", "יואב", "יובל",
    "יוחאי", "יונתן", "יוסי", "יוסף", "יורם", "ישי", "ישראל", "לירון", "מאור",
    "מיכאל", "מנחם", "מעיין", "משה", "נדב", "נועם", "ניר", "ניצן", "נתן",
    "עדי", "עידו", "עמית", "עמרי", "ערן", "פלג", "צחי", "קובי", "רון",
    "רועי", "רז", "שי", "שגיא", "שחר", "שלומי", "שלמה", "שמואל", "שמעון",
    "תום", "תומר",
    # English transliterations
    "avi", "aviv", "eyal", "itai", "itan", "alon", "eli", "amir", "erez",
    "ariel", "boaz", "gad", "gideon", "guy", "gil", "david", "dor", "dani",
    "daniel", "dan", "ziv", "hai", "haim", "yair", "yonatan", "yoav", "yuval",
    "yosef", "yossi", "moshe", "nadav", "noam", "nir", "nitzan", "natan",
    "adi", "ido", "amit", "omri", "eran", "kobi", "ron", "roi", "raz",
    "shai", "tom", "tomer",
}

HEBREW_FEMALE_NAMES = {
    # Common female names
    "אביגיל", "אבישג", "אורה", "אורית", "אורלי", "אילנה", "אילת", "איריס",
    "אסתר", "אפרת", "ברכה", "גאולה", "גילה", "דבורה", "דליה", "דנה", "דנית",
    "דפנה", "הגר", "הדס", "הדסה", "הילה", "חגית", "חוה", "חנה", "טל", "טלי",
    "יהודית", "יעל", "יפה", "יפית", "ירדן", "ירדנה", "כרמל", "כרמית", "לאה",
    "לי", "ליאור", "ליאורה", "ליאת", "לימור", "לירון", "מאיה", "מור", "מורן",
    "מיכל", "מירב", "מירי", "מיתר", "נגה", "נועה", "נופר", "נורית", "נטלי",
    "סיגל", "סיון", "עדי", "עדן", "עדנה", "ענבל", "ענת", "עפרה", "פנינה",
    "צופיה", "קרן", "רבקה", "רוית", "רונית", "רות", "רחל", "רינת", "שולמית",
    "שחר", "שי", "שיר", "שירה", "שירי", "שלומית", "שני", "שרה", "שרון",
    "תאיר", "תהילה", "תמר", "תמי",
    # English transliterations
    "avigail", "orit", "orli", "ilana", "iris", "efrat", "gila", "dalia",
    "dana", "danit", "dafna", "hagar", "hadas", "hila", "hagit", "hava",
    "chana", "tal", "tali", "yael", "yarden", "carmel", "lee", "lior",
    "liora", "liat", "limor", "maya", "mor", "moran", "michal", "merav",
    "miri", "noga", "noa", "nofar", "natali", "sigal", "sivan", "adi",
    "eden", "inbal", "anat", "ofra", "keren", "rivka", "ronit", "ruth",
    "rachel", "rinat", "shir", "shira", "shiri", "shani", "sara", "sharon",
    "tahel", "tamar", "tami",
}


class GenderDetector:
    """Detects gender from first name using multiple methods."""

    def __init__(self):
        self._detector = gender_detector.Detector(case_sensitive=False)

    def detect(self, full_name: str) -> str:
        """
        Detect gender from a full name.

        Returns: 'male', 'female', or 'unknown'
        """
        if not full_name or not full_name.strip():
            return "unknown"

        # Extract first name
        first_name = full_name.strip().split()[0].lower()

        # Try Hebrew names first
        gender = self._check_hebrew_name(first_name)
        if gender != "unknown":
            logger.debug(f"Gender for '{first_name}' (Hebrew): {gender}")
            return gender

        # Try international name detector
        gender = self._check_international_name(first_name)
        if gender != "unknown":
            logger.debug(f"Gender for '{first_name}' (International): {gender}")
            return gender

        logger.debug(f"Could not determine gender for: {first_name}")
        return "unknown"

    def _check_hebrew_name(self, first_name: str) -> str:
        """Check against Hebrew names database."""
        # Check Hebrew characters
        if first_name in HEBREW_MALE_NAMES:
            return "male"
        if first_name in HEBREW_FEMALE_NAMES:
            return "female"

        # Check transliterated versions
        lower_name = first_name.lower()
        if lower_name in HEBREW_MALE_NAMES:
            return "male"
        if lower_name in HEBREW_FEMALE_NAMES:
            return "female"

        return "unknown"

    def _check_international_name(self, first_name: str) -> str:
        """Use gender-guesser library for international names."""
        result = self._detector.get_gender(first_name)

        # Map results to our categories
        if result in ("male", "mostly_male"):
            return "male"
        elif result in ("female", "mostly_female"):
            return "female"
        else:
            return "unknown"

    def detect_from_profile(self, profile: dict) -> str:
        """
        Detect gender from a LinkedIn profile dict.
        Tries multiple signals.
        """
        # Try pronouns if available (LinkedIn sometimes shows these)
        pronouns = profile.get("pronouns", "").lower()
        if "he/him" in pronouns or "הוא" in pronouns:
            return "male"
        if "she/her" in pronouns or "היא" in pronouns:
            return "female"

        # Fall back to name detection
        name = profile.get("name", "")
        return self.detect(name)


# Singleton instance
_detector = None


def get_gender_detector() -> GenderDetector:
    """Get singleton gender detector instance."""
    global _detector
    if _detector is None:
        _detector = GenderDetector()
    return _detector


def detect_gender(name: str) -> str:
    """Convenience function to detect gender from name."""
    return get_gender_detector().detect(name)
