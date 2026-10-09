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
"""
import base64
import binascii
from contextlib import asynccontextmanager

from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
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


@app.get("/results")
def results() -> dict:
    """Evaluation and attack results for the judges' page. Each part is null until its script has been run."""
    return load_results()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
