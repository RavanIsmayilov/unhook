"""Mask sensitive data before anything is stored or sent to an LLM. URLs/domains are kept."""
import re

# 13-19 digits, optionally separated by spaces/dashes (card numbers)
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
IBAN_RE = re.compile(r"\bAZ\d{2}[A-Z]{4}\d{20}\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# loose phone: starts with + or digit, 9-13 digits with spaces/dashes/parens between
PHONE_RE = re.compile(r"(?<![\w.])\+?\d[\d\s\-()]{7,}\d(?![\w])")

# OTP / PIN / CVV codes: 3-8 digits next to a keyword ("kod: 4821", "4821 kodu", "OTP 123456", "пароль 5521")
_OTP_WORDS = r"(?:kod\w*|code|otp|şifr\w*|sifr\w*|parol\w*|pin|cvv|cvc|код\w*|пароль|пин)"
OTP_AFTER_RE = re.compile(rf"(?i)(\b{_OTP_WORDS}\b[^\d\n]{{0,25}}?)(?<!\d)\d{{3,8}}(?!\d)")
OTP_BEFORE_RE = re.compile(rf"(?i)(?<!\d)\d{{3,8}}(?!\d)(\s*\b{_OTP_WORDS}\b)")


def _phone_sub(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group())
    return "[PHONE]" if 9 <= len(digits) <= 13 else match.group()


def redact(text: str) -> str:
    text = IBAN_RE.sub("[IBAN]", text)
    text = CARD_RE.sub("[CARD]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub(_phone_sub, text)
    text = OTP_AFTER_RE.sub(r"\1[OTP]", text)
    return OTP_BEFORE_RE.sub(r"[OTP]\1", text)


def find_phones(text: str) -> list[str]:
    """Phone numbers found in raw text (cards removed first so they aren't mistaken for phones)."""
    text = CARD_RE.sub(" ", IBAN_RE.sub(" ", text))
    found = []
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 9 <= len(digits) <= 13 and m.group().strip() not in found:
            found.append(m.group().strip())
    return found


def mask_phone(phone: str) -> str:
    """Keep only the first 4 and last 2 digits for display."""
    digits = re.sub(r"\D", "", phone)
    return f"{digits[:4]}***{digits[-2:]}" if len(digits) > 6 else "***"
