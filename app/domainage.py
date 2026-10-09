"""How old is a domain? Scam sites are usually registered days before the campaign; banks use old domains.

Uses the free RDAP service (rdap.org). It covers .com, .net, .org, .xyz, .top, .click, .site, .online, .club and
most new TLDs, but NOT .az (those domains are simply skipped). Never slows or breaks a check: strict timeout, every
failure means "unknown", and answers are cached.
"""
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone

import httpx

from app import settings
from app.clustering import GENERIC_DOMAINS
from app.linkcheck import load_config
from app.schemas import Link

NEW_DOMAIN_DAYS = 30
NOT_FOUND_RECHECK = timedelta(hours=6)


def _conn() -> sqlite3.Connection:
    settings.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.CACHE_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS domain_reg (domain TEXT PRIMARY KEY, registered TEXT, checked_at TEXT NOT NULL)")
    return conn


def _cached(domain: str) -> tuple[bool, date | None]:
    """(known, registration date). A missing date is remembered for a few hours so we don't ask again and again."""
    with _conn() as conn:
        row = conn.execute("SELECT registered, checked_at FROM domain_reg WHERE domain = ?", (domain,)).fetchone()
    if not row:
        return False, None
    registered, checked_at = row
    if registered:
        return True, date.fromisoformat(registered)
    fresh = datetime.now(timezone.utc) - datetime.fromisoformat(checked_at) < NOT_FOUND_RECHECK
    return fresh, None


def _store(domain: str, registered: date | None) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO domain_reg VALUES (?, ?, ?)",
                     (domain, registered.isoformat() if registered else None, datetime.now(timezone.utc).isoformat()))


def registration_date(domain: str) -> date | None:
    known, cached = _cached(domain)
    if known:
        return cached
    registered = None
    try:
        response = httpx.get(f"https://rdap.org/domain/{domain}", timeout=settings.DOMAIN_AGE_TIMEOUT, follow_redirects=True)
        if response.status_code == 200:
            for event in response.json().get("events", []):
                if event.get("eventAction") == "registration":
                    registered = date.fromisoformat(event["eventDate"][:10])
                    break
        elif response.status_code != 404:
            return None  # rate-limited or a server error says nothing about the domain: do not remember it
    except (httpx.HTTPError, ValueError, KeyError) as e:
        print(f"[domainage] {domain}: {type(e).__name__}", file=sys.stderr)
        return None  # network trouble: don't remember it as "not found"
    _store(domain, registered)
    return registered


def age_days(domain: str, today: date | None = None) -> int | None:
    registered = registration_date(domain)
    return None if registered is None else max(0, ((today or date.today()) - registered).days)


def _worth_checking(link: Link) -> bool:
    cfg = load_config()
    return (link.status in ("lookalike", "suspicious", "unknown") and link.domain not in GENERIC_DOMAINS
            and link.domain not in cfg["shorteners"] and not link.domain.endswith(".az")
            and not link.domain.replace(".", "").isdigit())


def annotate(links: list[Link], max_links: int = 3) -> None:
    """Set link.age_days (in place) for the first few suspicious domains. A very new domain gets a flag, and an
    otherwise unremarkable link becomes 'suspicious'."""
    todo = [l for l in links if _worth_checking(l)][:max_links]
    if not todo:
        return
    pool = ThreadPoolExecutor(max_workers=len(todo))
    futures = {pool.submit(age_days, l.domain): l for l in todo}
    done, _ = wait(futures, timeout=settings.DOMAIN_AGE_TIMEOUT + 0.5)
    pool.shutdown(wait=False, cancel_futures=True)  # a slow lookup is simply abandoned
    for future in done:
        link = futures[future]
        try:
            link.age_days = future.result()
        except Exception:
            continue
        if link.age_days is not None and link.age_days < NEW_DOMAIN_DAYS:
            link.flags.append(f"new_domain:{link.age_days}d")
            if link.status == "unknown":
                link.status = "suspicious"
