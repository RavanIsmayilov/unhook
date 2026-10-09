"""Unhook API for the web demo and the fraud dashboard.

    uvicorn api:app --port 8000          (interactive docs: http://localhost:8000/docs)

POST /check           check a message / screenshot (same pipeline as the Telegram bot)
GET  /stats           overview numbers
GET  /campaigns       scam campaigns (grouped reports); ?brand=Azercell&min_reports=2&limit=50
GET  /reports/recent  latest redacted reports; ?limit=20
GET  /results         eval + attacker results (from results/*.json)
GET  /blocklist       suspicious domains for banks (?format=csv&brand=Azercell)
POST /feedback        'was this answer right?' from the website; GET /feedback/recent lists disagreements
GET  /health
POST /challenge, GET /challenge/stats   'fool the AI' game (stored apart from real reports)

Partner API (header X-API-Key; keys are made with partners.py):
GET  /partner/me, /partner/summary, /partner/campaigns, /partner/blocklist   (only the partner's own brand)
POST /partner/check, /partner/check/batch
"""
import base64
import binascii
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import db, settings
from app.blocklist import blocklist_csv, build_blocklist
from app.clustering import brands_of, build_campaigns
from app.redact import redact
from app.results import load_results
from app.schemas import SCHEME_AZ, Verdict
from app.service import check
from app.stats import compute_stats

MAX_IMAGE_BYTES = 5 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Unhook API", description="Get unhooked before you get scammed.", lifespan=lifespan)
# CORS lets the Next.js site (Vercel, or localhost:3000 in development) call us from the browser.
# It is not authentication: anyone can still call the API directly.
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
                   allow_methods=["*"], allow_headers=["*"])


class CheckRequest(BaseModel):
    text: str | None = Field(None, max_length=4000, description="The suspicious message")
    image_base64: str | None = Field(None, description="Screenshot as base64 (a data: URL prefix is accepted)")


class CheckResponse(Verdict):
    report_id: int | None = None


def _decode_image(data: str) -> bytes:
    if data.startswith("data:"):
        data = data.split(",", 1)[-1]
    try:
        image = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "image_base64 is not valid base64")
    if len(image) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "image is larger than 5 MB")
    return image


@app.post("/check", response_model=CheckResponse)
def check_message(req: CheckRequest) -> CheckResponse:
    """Plain `def`: FastAPI runs it in a thread pool, so the blocking LLM call doesn't stall the server."""
    text = (req.text or "").strip()
    image = _decode_image(req.image_base64) if req.image_base64 else None
    if not text and not image:
        raise HTTPException(422, "send text, image_base64, or both")
    verdict, report_id = check(text, image, source="api")
    return CheckResponse(**verdict.model_dump(), report_id=report_id)


@app.get("/stats")
def stats() -> dict:
    reports = db.all_reports()
    return {**compute_stats(reports, build_campaigns(reports)), "feedback": db.feedback_counts()}


@app.get("/campaigns")
def campaigns(min_reports: int = Query(2, ge=1), limit: int = Query(50, ge=1, le=200),
              brand: str | None = Query(None, description="only campaigns impersonating this brand")) -> list[dict]:
    found = build_campaigns(db.all_reports(), min_reports=min_reports)
    if brand:
        found = [c for c in found if brand.lower() in (b.lower() for b in c["brands"])]
    return found[:limit]


@app.get("/reports/recent")
def recent(limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    out = []
    for r in db.recent_reports(limit):
        r["scheme_az"] = SCHEME_AZ.get(r["scheme"], r["scheme"])
        r["brands"] = brands_of(r)
        out.append(r)
    return out


class FeedbackRequest(BaseModel):
    report_id: int
    agrees: bool = Field(description="True if the person thinks our verdict was right")
    suggested: Literal["scam", "safe"] | None = Field(None, description="What the message really is, when agrees is false")
    note: str | None = Field(None, max_length=500)


@app.post("/feedback")
def feedback(req: FeedbackRequest) -> dict:
    """'Was this answer right?' from the website. Disagreements are candidate test cases."""
    if not req.agrees and req.suggested is None:
        raise HTTPException(422, "say what the message really is (suggested) when you disagree")
    if not db.report_exists(req.report_id):
        raise HTTPException(404, "unknown report_id")
    return {"ok": True, "id": db.save_feedback(req.report_id, req.agrees, req.suggested, redact(req.note or ""))}


@app.get("/feedback/recent")
def feedback_recent(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    return db.recent_disagreements(limit)


@app.get("/blocklist")
def blocklist(format: Literal["json", "csv"] = "json", brand: str | None = Query(None), min_reports: int = Query(1, ge=1),
              limit: int = Query(200, ge=1, le=2000)):
    """Suspicious domains seen in scam reports. Automatic and unreviewed: check before blocking."""
    rows = build_blocklist(db.all_reports(), brand=brand, min_reports=min_reports)[:limit]
    if format == "csv":
        return Response(blocklist_csv(rows), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="unhook-blocklist.csv"'})
    return rows


# ---------------------------------------------------------------- partner API (X-API-Key)

def require_partner(x_api_key: str | None = Header(None, description="Your partner API key")) -> dict:
    if not x_api_key:
        raise HTTPException(401, "send your API key in the X-API-Key header")
    partner = db.get_partner_by_key(x_api_key.strip())
    if not partner:
        raise HTTPException(401, "invalid or revoked API key")
    return partner


def _own_brand(partner: dict, brands: list[str]) -> bool:
    return partner["brand"] is None or partner["brand"].lower() in (b.lower() for b in brands)


def _partner_reports(partner: dict) -> list[dict]:
    """Reports that impersonate the partner's brand (all reports for an 'all brands' partner)."""
    reports = db.all_reports()
    if partner["brand"] is None:
        return reports
    return [r for r in reports if _own_brand(partner, brands_of(r))]


MAX_BATCH = 10


class BatchRequest(BaseModel):
    messages: list[str] = Field(min_length=1, max_length=MAX_BATCH, description=f"1 to {MAX_BATCH} messages")


@app.get("/partner/me")
def partner_me(partner: dict = Depends(require_partner)) -> dict:
    return {"name": partner["name"], "brand": partner["brand"], "webhook": bool(partner["webhook_url"])}


@app.post("/partner/check", response_model=CheckResponse)
def partner_check(req: CheckRequest, partner: dict = Depends(require_partner)) -> CheckResponse:
    """Same as POST /check, for a partner's own systems (for example an SMS gateway)."""
    return check_message(req)


@app.post("/partner/check/batch")
def partner_check_batch(req: BatchRequest, partner: dict = Depends(require_partner)) -> list[dict]:
    """Check up to 10 messages in one request. Answers come back in the same order."""
    results = []
    for index, text in enumerate(req.messages):
        text = text.strip()[:4000]
        if not text:
            results.append({"index": index, "error": "empty message"})
            continue
        verdict, report_id = check(text, None, source="partner")
        results.append({"index": index, **CheckResponse(**verdict.model_dump(), report_id=report_id).model_dump()})
    return results


@app.get("/partner/summary")
def partner_summary(partner: dict = Depends(require_partner)) -> dict:
    """Numbers for the partner's own brand."""
    reports = _partner_reports(partner)
    threats = [r for r in reports if r["verdict"] in ("scam", "suspicious") and not r["degraded"]]
    camps = build_campaigns(reports)
    day_ago = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)).isoformat()
    return {
        "partner": {"name": partner["name"], "brand": partner["brand"]},
        "reports_total": len(threats),
        "reports_last_24h": sum(r["created_at"] >= day_ago for r in threats),
        "campaigns": len(camps),
        "campaigns_active_24h": sum(c["last_seen"] >= day_ago for c in camps),
        "blocklist_domains": len(build_blocklist(reports)),
    }


@app.get("/partner/campaigns")
def partner_campaigns(partner: dict = Depends(require_partner), min_reports: int = Query(1, ge=1),
                      limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    camps = build_campaigns(_partner_reports(partner), min_reports=min_reports)
    return [c for c in camps if _own_brand(partner, c["brands"])][:limit]


@app.get("/partner/blocklist")
def partner_blocklist(partner: dict = Depends(require_partner), format: Literal["json", "csv"] = "json",
                      limit: int = Query(500, ge=1, le=2000)):
    rows = [r for r in build_blocklist(_partner_reports(partner)) if _own_brand(partner, r["brands"])][:limit]
    if format == "csv":
        return Response(blocklist_csv(rows), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="unhook-blocklist.csv"'})
    return rows


# ---------------------------------------------------------------- "fool the AI" challenge

class ChallengeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000, description="A scam message written to slip past the detector")


@app.post("/challenge", response_model=CheckResponse)
def challenge(req: ChallengeRequest) -> CheckResponse:
    """Same analysis as /check, stored separately: these are made-up scams, not real reports."""
    text = req.text.strip()
    if not text:
        raise HTTPException(422, "write a message")
    verdict, report_id = check(text, None, source="challenge")
    return CheckResponse(**verdict.model_dump(), report_id=report_id)


@app.get("/challenge/stats")
def challenge_stats() -> dict:
    rows = [r for r in db.recent_reports(500, only_source="challenge") if not r["degraded"]]
    fooled = [r for r in rows if r["verdict"] == "safe"]
    unsure = [r for r in rows if r["verdict"] == "suspicious"]
    pick = lambda r: {"id": r["id"], "text": r["text_redacted"], "created_at": r["created_at"], "verdict": r["verdict"]}
    return {
        "attempts": len(rows), "fooled": len(fooled), "unsure": len(unsure), "caught": len(rows) - len(fooled) - len(unsure),
        "fooled_rate": len(fooled) / len(rows) if rows else None,
        "fooled_examples": [pick(r) for r in fooled[:10]],
        "recent": [pick(r) for r in rows[:10]],
    }


@app.get("/results")
def results() -> dict:
    """Evaluation and attack results for the judges' page. Each part is null until its script has been run."""
    return load_results()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
