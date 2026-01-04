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
# ~500+ names from Behind the Name database and other sources
ENGLISH_TO_HEBREW_NAMES = {
    # === A ===
    "aaron": "אהרון",
    "abigail": "אביגיל",
    "abraham": "אברהם",
    "adam": "אדם",
    "adara": "אדרה",
    "adi": "עדי",
    "adina": "עדינה",
    "adir": "אדיר",
    "adva": "אדוה",
    "agam": "אגם",
    "aharon": "אהרון",
    "ahava": "אהבה",
    "ahuva": "אהובה",
    "akiva": "עקיבא",
    "aliya": "עליה",
    "aliza": "עליזה",
    "alma": "עלמה",
    "almog": "אלמוג",
    "alon": "אלון",
    "alona": "אלונה",
    "ami": "עמי",
    "amichai": "עמיחי",
    "amir": "אמיר",
    "amit": "עמית",
    "amnon": "אמנון",
    "amos": "עמוס",
    "amram": "עמרם",
    "anan": "ענן",
    "anat": "ענת",
    "arie": "אריה",
    "ariel": "אריאל",
    "arik": "אריק",
    "arye": "אריה",
    "asa": "אסא",
    "asaf": "אסף",
    "asher": "אשר",
    "atalia": "עתליה",
    "atara": "עטרה",
    "avi": "אבי",
    "avia": "אביה",
    "aviad": "אביעד",
    "avidan": "אבידן",
    "aviel": "אביאל",
    "avigail": "אביגיל",
    "avigdor": "אביגדור",
    "avihu": "אביהוא",
    "aviram": "אבירם",
    "avishag": "אבישג",
    "avishai": "אבישי",
    "avital": "אביטל",
    "aviv": "אביב",
    "aviva": "אביבה",
    "avner": "אבנר",
    "avraham": "אברהם",
    "avram": "אברם",
    "avshalom": "אבשלום",
    "ayal": "איל",
    "ayala": "איילה",
    "ayelet": "איילת",
    "azaria": "עזריה",
    # === B ===
    "bar": "בר",
    "barak": "ברק",
    "baruch": "ברוך",
    "batel": "בת־אל",
    "batsheva": "בת־שבע",
    "batya": "בתיה",
    "beeri": "בארי",
    "benaya": "בניה",
    "beni": "בני",
    "benjamin": "בנימין",
    "benny": "בני",
    "beracha": "ברכה",
    "binyamin": "בנימין",
    "boaz": "בועז",
    "bosmat": "בשמת",
    "bracha": "ברכה",
    # === C ===
    "carmel": "כרמל",
    "carmit": "כרמית",
    "chaim": "חיים",
    "chana": "חנה",
    "chava": "חוה",
    "chaya": "חיה",
    "chen": "חן",
    "chesed": "חסד",
    # === D ===
    "dafna": "דפנה",
    "dalia": "דליה",
    "dalit": "דלית",
    "dan": "דן",
    "dana": "דנה",
    "dani": "דני",
    "daniel": "דניאל",
    "daniela": "דניאלה",
    "danit": "דנית",
    "danny": "דני",
    "danya": "דניה",
    "dar": "דר",
    "daphne": "דפנה",
    "david": "דוד",
    "deborah": "דבורה",
    "dekel": "דקל",
    "dikla": "דקלה",
    "dina": "דינה",
    "dor": "דור",
    "dori": "דורי",
    "dorit": "דורית",
    "doron": "דורון",
    "dov": "דוב",
    "dror": "דרור",
    "drorit": "דרורית",
    "dvora": "דבורה",
    # === E ===
    "eden": "עדן",
    "edna": "עדנה",
    "efraim": "אפרים",
    "efrat": "אפרת",
    "ehud": "אהוד",
    "eilat": "אילת",
    "eilon": "אילון",
    "eitan": "איתן",
    "elazar": "אלעזר",
    "elchanan": "אלחנן",
    "eldad": "אלדד",
    "eli": "אלי",
    "eliana": "אליענה",
    "eliav": "אליאב",
    "eliezer": "אליעזר",
    "elijah": "אליהו",
    "elior": "אליאור",
    "eliora": "אליאורה",
    "elisheva": "אלישבע",
    "eliya": "אליה",
    "eliyahu": "אליהו",
    "ephraim": "אפרים",
    "eran": "ערן",
    "erez": "ארז",
    "ester": "אסתר",
    "esther": "אסתר",
    "ethan": "איתן",
    "eve": "חוה",
    "eviatar": "אביתר",
    "evyatar": "אביתר",
    "eyal": "איל",
    "eytan": "איתן",
    "ezra": "עזרא",
    # === G ===
    "gad": "גד",
    "gai": "גיא",
    "gal": "גל",
    "gali": "גלי",
    "galia": "גליה",
    "galit": "גלית",
    "gavriel": "גבריאל",
    "gaya": "גאיה",
    "gefen": "גפן",
    "geula": "גאולה",
    "gideon": "גדעון",
    "gidon": "גדעון",
    "gil": "גיל",
    "gila": "גילה",
    "gilad": "גלעד",
    "gili": "גילי",
    "guy": "גיא",
    # === H ===
    "hadar": "הדר",
    "hadas": "הדס",
    "hadasa": "הדסה",
    "hadassa": "הדסה",
    "hadassah": "הדסה",
    "hagar": "הגר",
    "hagit": "חגית",
    "hai": "חי",
    "haim": "חיים",
    "hallel": "הלל",
    "hana": "חנה",
    "hannah": "חנה",
    "harel": "הראל",
    "hava": "חוה",
    "hayim": "חיים",
    "hed": "הד",
    "herut": "חרות",
    "hevel": "הבל",
    "hila": "הילה",
    "hili": "הילי",
    "hillel": "הלל",
    "hodia": "הודיה",
    "hyam": "חיים",
    # === I ===
    "idan": "עידן",
    "ido": "עידו",
    "ilai": "עילאי",
    "ilan": "אילן",
    "ilana": "אילנה",
    "ilanit": "אילנית",
    "ilat": "אילת",
    "immanuel": "עמנואל",
    "imri": "אמרי",
    "inbal": "ענבל",
    "inbar": "ענבר",
    "ira": "עירא",
    "iris": "איריס",
    "irit": "עירית",
    "israel": "ישראל",
    "itai": "איתי",
    "itamar": "איתמר",
    "itan": "איתן",
    "itay": "איתי",
    "itzhak": "יצחק",
    "iyov": "איוב",
    # === J ===
    "jardena": "ירדנה",
    "jonathan": "יונתן",
    "joseph": "יוסף",
    "judith": "יהודית",
    # === K ===
    "karmel": "כרמל",
    "kelila": "כלילה",
    "keren": "קרן",
    "keshet": "קשת",
    "kfir": "כפיר",
    "kineret": "כנרת",
    "kobi": "קובי",
    # === L ===
    "lavi": "לביא",
    "lea": "לאה",
    "leah": "לאה",
    "lee": "לי",
    "lev": "לב",
    "levana": "לבנה",
    "levi": "לוי",
    "li": "לי",
    "lian": "ליאן",
    "liat": "ליאת",
    "libi": "ליבי",
    "liel": "ליאל",
    "lihi": "ליהי",
    "lilach": "לילך",
    "limor": "לימור",
    "lior": "ליאור",
    "liora": "ליאורה",
    "liorit": "ליאורית",
    "liraz": "לירז",
    "liron": "לירון",
    "lital": "ליטל",
    "livna": "לבנה",
    "livnat": "לבנת",
    # === M ===
    "maayan": "מעיין",
    "malachi": "מלאכי",
    "malka": "מלכה",
    "maor": "מאור",
    "margalit": "מרגלית",
    "matan": "מתן",
    "matityahu": "מתתיהו",
    "maya": "מאיה",
    "meir": "מאיר",
    "meira": "מאירה",
    "meirit": "מאירית",
    "meital": "מיטל",
    "melech": "מלך",
    "menachem": "מנחם",
    "menahem": "מנחם",
    "menashe": "מנשה",
    "menuha": "מנוחה",
    "merav": "מירב",
    "meshulam": "משולם",
    "meyer": "מאיר",
    "michael": "מיכאל",
    "michaela": "מיכאלה",
    "michal": "מיכל",
    "mikhael": "מיכאל",
    "miri": "מירי",
    "miriam": "מרים",
    "mirit": "מירית",
    "miron": "מירון",
    "miryam": "מרים",
    "mor": "מור",
    "moran": "מורן",
    "mordecai": "מרדכי",
    "moria": "מוריה",
    "moshe": "משה",
    "moti": "מוטי",
    # === N ===
    "naama": "נעמה",
    "nachman": "נחמן",
    "nachum": "נחום",
    "nadav": "נדב",
    "naftali": "נפתלי",
    "nahal": "נחל",
    "naomi": "נעמי",
    "natan": "נתן",
    "nathan": "נתן",
    "nava": "נאוה",
    "nechama": "נחמה",
    "nehorai": "נהוראי",
    "neria": "נריה",
    "neta": "נטע",
    "netanel": "נתנאל",
    "netta": "נטע",
    "nili": "נילי",
    "nir": "ניר",
    "nitai": "ניתאי",
    "nitza": "ניצה",
    "nitzan": "ניצן",
    "niv": "ניב",
    "noa": "נועה",
    "noach": "נח",
    "noah": "נועה",
    "noam": "נועם",
    "nofar": "נופר",
    "noga": "נגה",
    "noy": "נוי",
    "noya": "נויה",
    "nurit": "נורית",
    # === O ===
    "odelia": "אודליה",
    "ofek": "אופק",
    "ofer": "עופר",
    "ofir": "אופיר",
    "ofira": "אופירה",
    "ofra": "עפרה",
    "ofri": "עפרי",
    "ohad": "אוהד",
    "omer": "עומר",
    "omri": "עמרי",
    "ophir": "אופיר",
    "or": "אור",
    "ora": "אורה",
    "orel": "אוראל",
    "oren": "אורן",
    "ori": "אורי",
    "orit": "אורית",
    "orli": "אורלי",
    "orna": "ארנה",
    "osher": "אושר",
    "oz": "עוז",
    # === P ===
    "paz": "פז",
    "peleg": "פלג",
    "pnina": "פנינה",
    # === R ===
    "raanan": "רענן",
    "rachel": "רחל",
    "rani": "רני",
    "ravid": "רביד",
    "ravit": "רוית",
    "raz": "רז",
    "rebecca": "רבקה",
    "reuben": "ראובן",
    "reut": "רעות",
    "rina": "רינה",
    "rinat": "רינת",
    "rivka": "רבקה",
    "roi": "רועי",
    "rom": "רום",
    "romi": "רומי",
    "ron": "רון",
    "rona": "רונה",
    "ronen": "רונן",
    "roni": "רוני",
    "ronit": "רונית",
    "rotem": "רותם",
    "roy": "רועי",
    "rut": "רות",
    "ruth": "רות",
    # === S ===
    "saar": "סער",
    "sagi": "שגיא",
    "sagit": "שגית",
    "samuel": "שמואל",
    "sapir": "ספיר",
    "sara": "שרה",
    "sarah": "שרה",
    "sarit": "שרית",
    "shachar": "שחר",
    "shai": "שי",
    "shaked": "שקד",
    "shalev": "שלו",
    "shalom": "שלום",
    "shamira": "שמירה",
    "shani": "שני",
    "sharon": "שרון",
    "shaul": "שאול",
    "shay": "שי",
    "shifra": "שפרה",
    "shimon": "שמעון",
    "shimshon": "שמשון",
    "shir": "שיר",
    "shira": "שירה",
    "shiri": "שירי",
    "shirli": "שירלי",
    "shlomi": "שלומי",
    "shlomit": "שלומית",
    "shlomo": "שלמה",
    "shmuel": "שמואל",
    "shoshana": "שושנה",
    "shulamit": "שולמית",
    "sigal": "סיגל",
    "simcha": "שמחה",
    "simon": "שמעון",
    "sivan": "סיון",
    "smadar": "סמדר",
    "solomon": "שלמה",
    "sophia": "צופיה",
    "stav": "סתיו",
    # === T ===
    "tahel": "תהל",
    "tair": "תאיר",
    "tal": "טל",
    "tali": "טלי",
    "talia": "טליה",
    "tam": "תם",
    "tamar": "תמר",
    "tami": "תמי",
    "tamir": "תמיר",
    "tehila": "תהילה",
    "tikva": "תקוה",
    "tirtza": "תרצה",
    "tohar": "טוהר",
    "tom": "תום",
    "tomer": "תומר",
    "tova": "טובה",
    "tovia": "טוביה",
    "tuvya": "טוביה",
    "tzachi": "צחי",
    "tzafrir": "צפריר",
    "tzila": "צילה",
    "tzion": "ציון",
    "tzipora": "ציפורה",
    "tzippora": "ציפורה",
    "tzivya": "צביה",
    "tzvi": "צבי",
    "tzvia": "צביה",
    "tzofia": "צופיה",
    # === U ===
    "udi": "אודי",
    "uri": "אורי",
    "uria": "אוריה",
    "uriel": "אוריאל",
    "uzi": "עוזי",
    # === V ===
    "varda": "ורדה",
    "vered": "ורד",
    # === Y ===
    "yaakov": "יעקב",
    "yaara": "יערה",
    "yael": "יעל",
    "yaen": "יען",
    "yafa": "יפה",
    "yafit": "יפית",
    "yahav": "יהב",
    "yair": "יאיר",
    "yakira": "יקירה",
    "yakov": "יעקב",
    "yali": "יהלי",
    "yam": "ים",
    "yanai": "ינאי",
    "yaniv": "יניב",
    "yarden": "ירדן",
    "yardena": "ירדנה",
    "yaron": "ירון",
    "yarona": "ירונה",
    "yasmin": "יסמין",
    "yechezkel": "יחזקאל",
    "yechiel": "יחיאל",
    "yedidya": "ידידיה",
    "yehonatan": "יהונתן",
    "yehoshua": "יהושע",
    "yehuda": "יהודה",
    "yehudi": "יהודי",
    "yehudit": "יהודית",
    "yemima": "ימימה",
    "yeshayahu": "ישעיהו",
    "yiftach": "יפתח",
    "yigal": "יגאל",
    "yinon": "ינון",
    "yishai": "ישי",
    "yisrael": "ישראל",
    "yissakhar": "יששכר",
    "yitzhak": "יצחק",
    "yoav": "יואב",
    "yochanan": "יוחנן",
    "yochai": "יוחאי",
    "yocheved": "יוכבד",
    "yoel": "יואל",
    "yona": "יונה",
    "yonatan": "יונתן",
    "yoni": "יוני",
    "yonina": "יונינה",
    "yonit": "יונית",
    "yoram": "יורם",
    "yosef": "יוסף",
    "yosi": "יוסי",
    "yossi": "יוסי",
    "yuli": "יולי",
    "yuval": "יובל",
    # === Z ===
    "zahara": "זהרה",
    "zeev": "זאב",
    "ziv": "זיו",
    "ziva": "זיוה",
    "zivit": "זיוית",
    "zohar": "זוהר",
    # === Additional common variants ===
    "natali": "נטלי",
    "natalie": "נטלי",
}

# Runtime cache for database translations (populated by async functions)
# This allows the sync function to access DB translations without async DB calls
_db_translations_cache: dict[str, str] = {}


def add_to_cache(english_name: str, hebrew_name: str) -> None:
    """Add a translation to the runtime cache for sync access."""
    _db_translations_cache[english_name.lower()] = hebrew_name
    logger.debug(f"Added to cache: {english_name.lower()} -> {hebrew_name}")


def translate_name_to_hebrew_sync(english_name: str) -> str | None:
    """
    Translate an English name to Hebrew script (synchronous).

    Checks:
    1. Built-in dictionary
    2. Runtime cache (populated from DB by async functions)

    Args:
        english_name: Name in English (e.g., "Tomer")

    Returns:
        Hebrew name if found, None otherwise
    """
    if not english_name:
        return None

    # Extract first name and normalize
    first_name = english_name.strip().split()[0].lower()

    # Check if already in Hebrew (contains Hebrew characters)
    if any('\u0590' <= char <= '\u05FF' for char in first_name):
        logger.debug(f"Name '{english_name}' is already in Hebrew")
        return english_name.split()[0]  # Return original first name

    # 1. Look up in built-in dictionary
    hebrew_name = ENGLISH_TO_HEBREW_NAMES.get(first_name)
    if hebrew_name:
        logger.debug(f"Translated '{first_name}' to Hebrew from dict: {hebrew_name}")
        return hebrew_name

    # 2. Look up in runtime cache (populated from DB)
    hebrew_name = _db_translations_cache.get(first_name)
    if hebrew_name:
        logger.debug(f"Translated '{first_name}' to Hebrew from cache: {hebrew_name}")
        return hebrew_name

    # Name not found
    logger.debug(f"No Hebrew translation found for '{first_name}'")
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

    # 2. Check runtime cache (populated from DB)
    cached = _db_translations_cache.get(first_name)
    if cached:
        logger.debug(f"Translated '{first_name}' to Hebrew from cache: {cached}")
        return cached

    # 3. Check database for user-provided translation
    result = await db.execute(
        select(HebrewName).where(HebrewName.english_name == first_name)
    )
    db_entry = result.scalar_one_or_none()

    if db_entry:
        # Add to cache for sync access
        add_to_cache(first_name, db_entry.hebrew_name)
        logger.debug(f"Translated '{first_name}' to Hebrew from DB: {db_entry.hebrew_name}")
        return db_entry.hebrew_name

    # Name not found anywhere
    logger.info(f"No Hebrew translation found for '{first_name}'")
    return None


async def save_hebrew_name(english_name: str, hebrew_name: str, db: AsyncSession) -> HebrewName:
    """
    Save a user-provided Hebrew name translation to the database.

    Also adds to the runtime cache for immediate sync access.

    Args:
        english_name: English name (will be lowercased)
        hebrew_name: Hebrew translation
        db: Database session

    Returns:
        The created HebrewName record
    """
    english_lower = english_name.strip().lower()

    # Add to runtime cache immediately (so sync functions can access it)
    add_to_cache(english_lower, hebrew_name)

    # Check if already exists in DB
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


async def load_all_translations_to_cache(db: AsyncSession) -> int:
    """
    Load all database translations into the runtime cache.

    Call this at startup to ensure sync functions can access DB translations.

    Args:
        db: Database session

    Returns:
        Number of translations loaded
    """
    result = await db.execute(select(HebrewName))
    entries = result.scalars().all()

    count = 0
    for entry in entries:
        add_to_cache(entry.english_name, entry.hebrew_name)
        count += 1

    if count > 0:
        logger.info(f"Loaded {count} Hebrew name translations from database to cache")

    return count
