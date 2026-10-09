"""Group reports into scam campaigns.

Two signals, merged with union-find:
  1. similar text: TF-IDF on character n-grams + DBSCAN (cosine). Char n-grams survive spelling variants, and we fold
     Azerbaijani letters (ə->e, ş->s, ...) so "qazandınız" and "qazandiniz" look alike.
  2. the same non-official domain (shorteners and generic sites like t.me are ignored).
"""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from app.linkcheck import load_config
from app.schemas import SCHEME_AZ

EPS = 0.7  # cosine distance; tuned on data/labeled.csv: the 3 writings of one message merge, different messages don't
FOLD = str.maketrans({"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ş": "s", "ç": "c", "ğ": "g", "İ": "i"})
PLACEHOLDER_RE = re.compile(r"\[(?:phone|otp|card|iban|email)\]", re.IGNORECASE)
GENERIC_DOMAINS = {"t.me", "wa.me", "telegram.org", "whatsapp.com", "instagram.com", "facebook.com", "google.com",
                   "forms.gle", "youtube.com", "youtu.be"}


def normalize(text: str) -> str:
    text = PLACEHOLDER_RE.sub(" ", text.replace("İ", "i").lower().translate(FOLD))  # lower() would leave 'i' + a combining dot
    return re.sub(r"\s+", " ", text).strip()


def campaign_domains(report: dict) -> list[str]:
    """Domains that can tie reports together: not official, not a URL shortener, not a generic site."""
    shorteners = set(load_config()["shorteners"])
    return [l["domain"] for l in report.get("links", [])
            if l["status"] not in ("official", "shortener") and l["domain"] not in GENERIC_DOMAINS
            and l["domain"] not in shorteners]


def brands_of(report: dict) -> list[str]:
    """Brands the message impersonates, taken from the link checker's flags."""
    by_domain = {d: b["name"] for b in load_config()["brands"] for d in b["domains"]}
    brands: list[str] = []
    for link in report.get("links", []):
        for flag in link.get("flags", []):
            kind, _, value = flag.partition(":")
            brand = value if kind == "brand_in_domain" else by_domain.get(value) if kind == "similar_to" else None
            if brand and brand not in brands:
                brands.append(brand)
    return brands


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        self.parent[self.find(a)] = self.find(b)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def build_campaigns(reports: list[dict], eps: float = EPS, min_reports: int = 2,
                    now: datetime | None = None) -> list[dict]:
    """reports: dicts as returned by db.recent_reports(). Returns campaigns, biggest first."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [r for r in reports if r["verdict"] in ("scam", "suspicious") and not r["degraded"] and r["text_redacted"].strip()]
    if len(rows) < max(2, min_reports):
        return []

    uf = _UnionFind(len(rows))
    vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit_transform(
        [normalize(r["text_redacted"]) for r in rows])
    labels = DBSCAN(eps=eps, min_samples=2, metric="cosine").fit_predict(vectors)
    first_in_cluster: dict[int, int] = {}
    for i, label in enumerate(labels):
        if label != -1:
            uf.union(i, first_in_cluster.setdefault(label, i))
    first_with_domain: dict[str, int] = {}
    for i, r in enumerate(rows):
        for d in campaign_domains(r):
            uf.union(i, first_with_domain.setdefault(d, i))

    groups: dict[int, list[dict]] = {}
    for i, r in enumerate(rows):
        groups.setdefault(uf.find(i), []).append(r)

    campaigns = [_describe(sorted(g, key=lambda r: (r["created_at"], r["id"])), now)
                 for g in groups.values() if len(g) >= min_reports]
    return sorted(campaigns, key=lambda c: (c["count"], c["last_seen"]), reverse=True)


def _describe(members: list[dict], now: datetime) -> dict:
    schemes = Counter(r["scheme"] for r in members if r["scheme"] not in ("none", "other"))
    scheme = schemes.most_common(1)[0][0] if schemes else Counter(r["scheme"] for r in members).most_common(1)[0][0]
    domains = [d for d, _ in Counter(d for r in members for d in set(campaign_domains(r))).most_common()]
    brands = [b for b, _ in Counter(b for r in members for b in set(brands_of(r))).most_common()]
    name = " · ".join([SCHEME_AZ.get(scheme, SCHEME_AZ["other"])] + brands[:1] + domains[:1])
    example = max(members, key=lambda r: (r["confidence"], -r["id"]))
    day_ago = (now - timedelta(hours=24)).isoformat()
    return {
        "id": f"C{members[0]['id']}",
        "name": name,
        "scheme": scheme,
        "scheme_az": SCHEME_AZ.get(scheme, SCHEME_AZ["other"]),
        "count": len(members),
        "reports_last_24h": sum(r["created_at"] >= day_ago for r in members),
        "first_seen": members[0]["created_at"],
        "last_seen": members[-1]["created_at"],
        "example": example["text_redacted"],
        "domains": domains,
        "brands": brands,
        "verdicts": dict(Counter(r["verdict"] for r in members)),
        "report_ids": [r["id"] for r in members],
    }
