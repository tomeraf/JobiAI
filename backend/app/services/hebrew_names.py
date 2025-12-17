"""
Hebrew name translator - converts English transliterations to Hebrew script.

This is needed because LinkedIn shows names in English transliteration,
but we want to send messages in Hebrew with the name in Hebrew script.

Names are looked up in:
1. Built-in dictionary of common Hebrew names
2. Database table of user-provided translations

If a name is not found, return None to signal the workflow should pause.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hebrew_name import HebrewName
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Mapping of English transliterations to Hebrew names
# Format: english_lowercase -> hebrew_script
ENGLISH_TO_HEBREW_NAMES = {
    # Male names
    "avi": "אבי",
    "aviv": "אביב",
    "avigdor": "אביגדור",
    "aviad": "אביעד",
    "aviram": "אבירם",
    "avishai": "אבישי",
    "avraham": "אברהם",
    "abraham": "אברהם",
    "adam": "אדם",
    "aharon": "אהרון",
    "aaron": "אהרון",
    "uri": "אורי",
    "oren": "אורן",
    "eyal": "אייל",
    "itai": "איתי",
    "itay": "איתי",
    "itan": "איתן",
    "ethan": "איתן",
    "alon": "אלון",
    "eli": "אלי",
    "eliyahu": "אליהו",
    "amir": "אמיר",
    "erez": "ארז",
    "ariel": "אריאל",
    "arie": "אריה",
    "asher": "אשר",
    "boaz": "בועז",
    "beni": "בני",
    "benny": "בני",
    "benjamin": "בנימין",
    "binyamin": "בנימין",
    "gad": "גד",
    "gideon": "גדעון",
    "guy": "גיא",
    "gil": "גיל",
    "gilad": "גלעד",
    "david": "דוד",
    "dor": "דור",
    "dani": "דני",
    "danny": "דני",
    "daniel": "דניאל",
    "dan": "דן",
    "harel": "הראל",
    "ziv": "זיו",
    "hai": "חי",
    "haim": "חיים",
    "chaim": "חיים",
    "yair": "יאיר",
    "yigal": "יגאל",
    "yehonatan": "יהונתן",
    "yehuda": "יהודה",
    "yoav": "יואב",
    "yuval": "יובל",
    "yochai": "יוחאי",
    "yonatan": "יונתן",
    "jonathan": "יונתן",
    "yosi": "יוסי",
    "yossi": "יוסי",
    "yosef": "יוסף",
    "joseph": "יוסף",
    "yoram": "יורם",
    "yishai": "ישי",
    "israel": "ישראל",
    "liron": "לירון",
    "maor": "מאור",
    "michael": "מיכאל",
    "menachem": "מנחם",
    "maayan": "מעיין",
    "moshe": "משה",
    "nadav": "נדב",
    "noam": "נועם",
    "nir": "ניר",
    "nitzan": "ניצן",
    "natan": "נתן",
    "nathan": "נתן",
    "adi": "עדי",
    "ido": "עידו",
    "amit": "עמית",
    "omri": "עמרי",
    "eran": "ערן",
    "peleg": "פלג",
    "tzachi": "צחי",
    "kobi": "קובי",
    "ron": "רון",
    "roi": "רועי",
    "roy": "רועי",
    "raz": "רז",
    "shai": "שי",
    "shay": "שי",
    "sagi": "שגיא",
    "shachar": "שחר",
    "shlomi": "שלומי",
    "shlomo": "שלמה",
    "solomon": "שלמה",
    "shmuel": "שמואל",
    "samuel": "שמואל",
    "shimon": "שמעון",
    "simon": "שמעון",
    "tom": "תום",
    "tomer": "תומר",

    # Female names
    "avigail": "אביגיל",
    "abigail": "אביגיל",
    "avishag": "אבישג",
    "ora": "אורה",
    "orit": "אורית",
    "orli": "אורלי",
    "ilana": "אילנה",
    "ilat": "אילת",
    "eilat": "אילת",
    "iris": "איריס",
    "esther": "אסתר",
    "efrat": "אפרת",
    "bracha": "ברכה",
    "geula": "גאולה",
    "gila": "גילה",
    "dvora": "דבורה",
    "deborah": "דבורה",
    "dalia": "דליה",
    "dana": "דנה",
    "danit": "דנית",
    "dafna": "דפנה",
    "daphne": "דפנה",
    "hagar": "הגר",
    "hadas": "הדס",
    "hadasa": "הדסה",
    "hadassa": "הדסה",
    "hila": "הילה",
    "hagit": "חגית",
    "hava": "חוה",
    "eve": "חוה",
    "chana": "חנה",
    "hana": "חנה",
    "hannah": "חנה",
    "tal": "טל",
    "tali": "טלי",
    "yehudit": "יהודית",
    "judith": "יהודית",
    "yael": "יעל",
    "yafa": "יפה",
    "yafit": "יפית",
    "yarden": "ירדן",
    "jardena": "ירדנה",
    "carmel": "כרמל",
    "carmit": "כרמית",
    "lea": "לאה",
    "leah": "לאה",
    "lee": "לי",
    "li": "לי",
    "lior": "ליאור",
    "liora": "ליאורה",
    "liat": "ליאת",
    "limor": "לימור",
    "maya": "מאיה",
    "mor": "מור",
    "moran": "מורן",
    "michal": "מיכל",
    "merav": "מירב",
    "miri": "מירי",
    "meitar": "מיתר",
    "noga": "נגה",
    "noa": "נועה",
    "noah": "נועה",
    "nofar": "נופר",
    "nurit": "נורית",
    "natali": "נטלי",
    "natalie": "נטלי",
    "sigal": "סיגל",
    "sivan": "סיון",
    "eden": "עדן",
    "edna": "עדנה",
    "inbal": "ענבל",
    "anat": "ענת",
    "ofra": "עפרה",
    "pnina": "פנינה",
    "tzofia": "צופיה",
    "sophia": "צופיה",
    "keren": "קרן",
    "rivka": "רבקה",
    "rebecca": "רבקה",
    "ravit": "רוית",
    "ronit": "רונית",
    "ruth": "רות",
    "rachel": "רחל",
    "rinat": "רינת",
    "shulamit": "שולמית",
    "shir": "שיר",
    "shira": "שירה",
    "shiri": "שירי",
    "shani": "שני",
    "sara": "שרה",
    "sarah": "שרה",
    "sharon": "שרון",
    "tair": "תאיר",
    "tehila": "תהילה",
    "tamar": "תמר",
    "tami": "תמי",

    # Unisex names (appear in both lists, use most common form)
    "chen": "חן",
    "omer": "עומר",
    "or": "אור",
    "yam": "ים",
    "gal": "גל",
    "noy": "נוי",
    "bar": "בר",
    "ofek": "אופק",
    "rotem": "רותם",
    "agam": "אגם",
    "shaked": "שקד",
}


def translate_name_to_hebrew_sync(english_name: str) -> str | None:
    """
    Translate an English name to Hebrew script (synchronous, dict-only).

    Args:
        english_name: Name in English (e.g., "Tomer")

    Returns:
        Hebrew name if found in built-in dictionary, None otherwise
    """
    if not english_name:
        return None

    # Extract first name and normalize
    first_name = english_name.strip().split()[0].lower()

    # Check if already in Hebrew (contains Hebrew characters)
    if any('\u0590' <= char <= '\u05FF' for char in first_name):
        logger.debug(f"Name '{english_name}' is already in Hebrew")
        return english_name.split()[0]  # Return original first name

    # Look up in dictionary
    hebrew_name = ENGLISH_TO_HEBREW_NAMES.get(first_name)

    if hebrew_name:
        logger.debug(f"Translated '{first_name}' to Hebrew: {hebrew_name}")
        return hebrew_name

    # Name not found in dictionary
    logger.debug(f"No Hebrew translation found for '{first_name}' in built-in dictionary")
    return None


async def translate_name_to_hebrew(english_name: str, db: AsyncSession) -> str | None:
    """
    Translate an English name to Hebrew script (async, with DB lookup).

    Args:
        english_name: Name in English (e.g., "Tomer")
        db: Database session

    Returns:
        Hebrew name if found (dict or DB), None if not found
    """
    if not english_name:
        return None

    # Extract first name and normalize
    first_name = english_name.strip().split()[0].lower()

    # Check if already in Hebrew (contains Hebrew characters)
    if any('\u0590' <= char <= '\u05FF' for char in first_name):
        logger.debug(f"Name '{english_name}' is already in Hebrew")
        return english_name.split()[0]

    # 1. Check built-in dictionary first
    hebrew_name = ENGLISH_TO_HEBREW_NAMES.get(first_name)
    if hebrew_name:
        logger.debug(f"Translated '{first_name}' to Hebrew from dictionary: {hebrew_name}")
        return hebrew_name

    # 2. Check database for user-provided translation
    result = await db.execute(
        select(HebrewName).where(HebrewName.english_name == first_name)
    )
    db_entry = result.scalar_one_or_none()

    if db_entry:
        logger.debug(f"Translated '{first_name}' to Hebrew from DB: {db_entry.hebrew_name}")
        return db_entry.hebrew_name

    # Name not found anywhere
    logger.info(f"No Hebrew translation found for '{first_name}'")
    return None


async def save_hebrew_name(english_name: str, hebrew_name: str, db: AsyncSession) -> HebrewName:
    """
    Save a user-provided Hebrew name translation to the database.

    Args:
        english_name: English name (will be lowercased)
        hebrew_name: Hebrew translation
        db: Database session

    Returns:
        The created HebrewName record
    """
    english_lower = english_name.strip().lower()

    # Check if already exists
    result = await db.execute(
        select(HebrewName).where(HebrewName.english_name == english_lower)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing
        existing.hebrew_name = hebrew_name
        logger.info(f"Updated Hebrew name: {english_lower} -> {hebrew_name}")
        return existing

    # Create new
    new_entry = HebrewName(
        english_name=english_lower,
        hebrew_name=hebrew_name,
    )
    db.add(new_entry)
    await db.flush()
    logger.info(f"Saved Hebrew name: {english_lower} -> {hebrew_name}")
    return new_entry


async def get_missing_hebrew_names(names: list[str], db: AsyncSession) -> list[str]:
    """
    Check which names from a list don't have Hebrew translations.

    Args:
        names: List of English names to check
        db: Database session

    Returns:
        List of names that need Hebrew translations
    """
    missing = []
    for name in names:
        hebrew = await translate_name_to_hebrew(name, db)
        if hebrew is None:
            # Extract first name
            first_name = name.strip().split()[0].lower()
            if first_name not in missing:
                missing.append(first_name)
    return missing


def is_hebrew_text(text: str) -> bool:
    """
    Check if text contains Hebrew characters.

    Args:
        text: Text to check

    Returns:
        True if text contains Hebrew characters
    """
    if not text:
        return False
    return any('\u0590' <= char <= '\u05FF' for char in text)
