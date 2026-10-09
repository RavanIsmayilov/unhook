"""Extract URLs from text and compare their domains with an allowlist of official domains."""
import re
from functools import lru_cache

import yaml

from app.schemas import Link
from app.settings import DOMAINS_PATH

SECOND_LEVELS = {"com", "co", "org", "net", "gov", "edu"}
HOMOGLYPHS = str.maketrans(
    {"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "ı": "i", "ə": "e", "ö": "o", "ü": "u", "ğ": "g", "ş": "s", "ç": "c"}
)


@lru_cache(maxsize=1)
def load_config() -> dict:
    return yaml.safe_load(DOMAINS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _url_regexes() -> tuple[re.Pattern, re.Pattern]:
    cfg = load_config()
    tlds = "|".join(sorted(set(cfg["known_tlds"] + cfg["suspicious_tlds"]), key=len, reverse=True))
    explicit = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
    bare = re.compile(rf"(?<![\w@./-])(?:[a-z0-9-]+\.)+(?:{tlds})(?![a-z0-9-])(?:/[^\s<>\"']*)?", re.IGNORECASE)
    return explicit, bare


def extract_urls(text: str) -> list[str]:
    explicit, bare = _url_regexes()
    urls: list[str] = []
    for m in explicit.finditer(text):
        urls.append(m.group())
    # bare domains like "bonus-azercell.top/claim"; skip ones already inside an explicit URL
    for m in bare.finditer(text):
        if not any(m.group() in u for u in urls):
            urls.append(m.group())
    cleaned = [u.rstrip(".,;:!?)]}\"'") for u in urls]
    return list(dict.fromkeys(cleaned))


def parse_host(url: str) -> tuple[str, bool]:
    """Return (host, has_userinfo_trick)."""
    rest = re.sub(r"^[a-z]+://", "", url, flags=re.IGNORECASE)
    authority = re.split(r"[/?#]", rest, maxsplit=1)[0]
    userinfo = "@" in authority
    host = authority.rsplit("@", 1)[-1].split(":")[0].lower()
    return host.removeprefix("www."), userinfo


def registrable(host: str) -> str:
    labels = host.split(".")
    if len(labels) >= 3 and labels[-2] in SECOND_LEVELS and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def sld(domain: str) -> str:
    """Second-level label: 'azercell.com' -> 'azercell'; 'asan.gov.az' -> 'asan'."""
    labels = registrable(domain).split(".")
    return labels[-3] if len(labels) == 3 else labels[0]


def normalize(label: str) -> str:
    label = label.lower().translate(HOMOGLYPHS)
    return label.replace("rn", "m").replace("vv", "w").replace("-", "")


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def is_official(host: str, cfg: dict) -> bool:
    for brand in cfg["brands"]:
        for d in brand["domains"]:
            if host == d or host.endswith("." + d):
                return True
    return any(host.endswith("." + s) for s in cfg["official_suffixes"])


def check_url(url: str) -> Link:
    cfg = load_config()
    host, userinfo = parse_host(url)
    flags: list[str] = []

    if not host or "." not in host:
        return Link(url=url, domain=host, status="unknown", flags=["unparseable"])

    reg = registrable(host)
    if is_official(host, cfg) and not userinfo:
        return Link(url=url, domain=reg, status="official")

    if userinfo:
        flags.append("userinfo_trick")
    if reg in cfg["shorteners"]:
        flags.append("url_shortener")
    if host.startswith("xn--") or ".xn--" in host:
        flags.append("punycode")
    if re.fullmatch(r"[\d.]+", host):
        flags.append("ip_address")

    tld = reg.split(".")[-1]
    if tld in cfg["suspicious_tlds"]:
        flags.append(f"suspicious_tld:.{tld}")

    name = sld(reg)
    tokens = [t for t in re.split(r"[.\-_]", host) if t]
    for word in cfg["suspicious_words"]:
        if word in host.replace(".", " ").replace("-", " "):
            flags.append(f"suspicious_word:{word}")

    lookalike = False
    for brand in cfg["brands"]:
        # brand name embedded in the host (long keywords as substring, short ones as an exact token)
        for kw in brand["keywords"]:
            if (len(kw) >= 5 and kw in host) or kw in tokens:
                flags.append(f"brand_in_domain:{brand['name']}")
                lookalike = True
                break
        # near-identical spelling of an official domain (azercel.com, azerce11.com, azercell.top)
        for d in brand["domains"]:
            official_name = normalize(sld(d))
            if len(official_name) < 5:
                continue
            dist = edit_distance(normalize(name), official_name)
            limit = 1 if len(official_name) < 8 else 2
            if dist <= limit:
                flags.append(f"similar_to:{d}")
                lookalike = True
    flags = list(dict.fromkeys(flags))

    if "url_shortener" in flags:
        status = "shortener"
    elif lookalike:
        status = "lookalike"
    elif flags:
        status = "suspicious"
    else:
        status = "unknown"
    return Link(url=url, domain=reg, status=status, flags=flags)


def check_links(text: str) -> list[Link]:
    return [check_url(u) for u in extract_urls(text)]
