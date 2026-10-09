"""SQLite storage. Only redacted data is ever stored: no raw text, no card/phone/OTP, no full URLs."""
import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app import settings
from app.schemas import Verdict

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    source: Mapped[str] = mapped_column(String(20))  # "telegram" | "api"
    had_image: Mapped[bool] = mapped_column(Boolean, default=False)
    text_redacted: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(12), index=True)
    scheme: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(JSON)
    actions: Mapped[list] = mapped_column(JSON)
    explanation_az: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[list] = mapped_column(JSON)  # [{"domain", "status", "flags"}] - no full URLs
    domains: Mapped[list] = mapped_column(JSON)  # unique domains, used for campaigns
    provider: Mapped[str] = mapped_column(String(20), default="")
    model: Mapped[str] = mapped_column(String(60), default="")
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        d["created_at"] = self.created_at.isoformat()
        return d


class Feedback(Base):
    """A person's verdict on our verdict. `suggested` is what they say the message really is (only when they disagree)."""
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    report_id: Mapped[int] = mapped_column(Integer, index=True)
    agrees: Mapped[bool] = mapped_column(Boolean)
    suggested: Mapped[str | None] = mapped_column(String(12), nullable=True)  # "scam" | "safe"
    note: Mapped[str] = mapped_column(Text, default="")


class Partner(Base):
    """A company (bank, telecom) that calls the API with its own key and may see only its own brand."""
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    brand: Mapped[str | None] = mapped_column(String(80), nullable=True)  # None = sees every brand
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # we never store the key itself
    key_prefix: Mapped[str] = mapped_column(String(16))
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_secret: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def save_report(v: Verdict, source: str, had_image: bool = False, created_at: datetime | None = None) -> int:
    links = [{"domain": l.domain, "status": l.status, "flags": l.flags} for l in v.links]
    report = Report(
        source=source, had_image=had_image, text_redacted=v.text_redacted, verdict=v.verdict, scheme=v.scheme,
        confidence=v.confidence, reasons=v.reasons, actions=v.actions, explanation_az=v.explanation_az,
        links=links, domains=list(dict.fromkeys(l["domain"] for l in links if l["domain"])),
        provider=v.provider, model=v.model, degraded=v.degraded,
    )
    if created_at:
        report.created_at = created_at
    with Session(engine) as session:
        session.add(report)
        session.commit()
        return report.id


# Messages typed into the "fool the AI" challenge are made-up scams, so they must never show up as real reports.
HIDDEN_SOURCES = ("challenge",)


def recent_reports(limit: int = 50, only_source: str | None = None) -> list[dict]:
    with Session(engine) as session:
        query = select(Report).order_by(Report.created_at.desc(), Report.id.desc()).limit(limit)
        query = query.where(Report.source == only_source) if only_source else query.where(Report.source.not_in(HIDDEN_SOURCES))
        return [r.to_dict() for r in session.scalars(query)]


def all_reports(limit: int = 5000) -> list[dict]:
    """Newest first. Used for stats and campaign clustering."""
    return recent_reports(limit)


def delete_reports(source: str) -> int:
    with Session(engine) as session:
        rows = session.scalars(select(Report).where(Report.source == source)).all()
        for r in rows:
            session.delete(r)
        session.commit()
        return len(rows)


def report_exists(report_id: int) -> bool:
    with Session(engine) as session:
        return session.get(Report, report_id) is not None


def save_feedback(report_id: int, agrees: bool, suggested: str | None = None, note: str = "") -> int:
    row = Feedback(report_id=report_id, agrees=agrees, suggested=None if agrees else suggested, note=note)
    with Session(engine) as session:
        session.add(row)
        session.commit()
        return row.id


def feedback_counts() -> dict:
    with Session(engine) as session:
        rows = session.scalars(select(Feedback)).all()
    agree = sum(r.agrees for r in rows)
    return {"total": len(rows), "agree": agree, "disagree": len(rows) - agree}


def recent_disagreements(limit: int = 20) -> list[dict]:
    """Where a person said our verdict was wrong, with the (redacted) message and what we answered."""
    with Session(engine) as session:
        rows = session.execute(
            select(Feedback, Report).join(Report, Report.id == Feedback.report_id)
            .where(Feedback.agrees.is_(False)).order_by(Feedback.created_at.desc(), Feedback.id.desc()).limit(limit)
        ).all()
        return [{"id": f.id, "created_at": f.created_at.isoformat(), "report_id": r.id, "model_verdict": r.verdict,
                 "suggested": f.suggested, "scheme": r.scheme, "text_redacted": r.text_redacted, "note": f.note}
                for f, r in rows]


# ---------------------------------------------------------------- partners (API keys)

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _partner_dict(p: Partner, secret: bool = False) -> dict:
    d = {"id": p.id, "name": p.name, "brand": p.brand, "key_prefix": p.key_prefix, "webhook_url": p.webhook_url,
         "active": p.active, "created_at": p.created_at.isoformat()}
    if secret:
        d["webhook_secret"] = p.webhook_secret
    return d


def create_partner(name: str, brand: str | None = None, webhook_url: str | None = None, replace: bool = False) -> tuple[dict, str]:
    """Returns (partner, api_key). The key is shown once: only its hash is stored."""
    key = "unhook_" + secrets.token_urlsafe(24)
    with Session(engine) as session:
        old = session.scalars(select(Partner).where(Partner.name == name)).first()
        if old and not replace:
            raise ValueError(f"a partner named {name!r} already exists")
        if old:
            session.delete(old)
            session.flush()
        p = Partner(name=name, brand=brand or None, key_hash=_hash_key(key), key_prefix=key[:12],
                    webhook_url=webhook_url or None, webhook_secret=secrets.token_hex(16))
        session.add(p)
        session.commit()
        return _partner_dict(p, secret=True), key


def get_partner_by_key(key: str) -> dict | None:
    with Session(engine) as session:
        p = session.scalars(select(Partner).where(Partner.key_hash == _hash_key(key), Partner.active.is_(True))).first()
        return _partner_dict(p) if p else None


def list_partners() -> list[dict]:
    with Session(engine) as session:
        return [_partner_dict(p) for p in session.scalars(select(Partner).order_by(Partner.id))]


def revoke_partner(name: str) -> bool:
    with Session(engine) as session:
        p = session.scalars(select(Partner).where(Partner.name == name)).first()
        if not p:
            return False
        p.active = False
        session.commit()
        return True


def webhook_partners() -> list[dict]:
    """Active partners that asked for webhooks, including the secret used to sign them."""
    with Session(engine) as session:
        rows = session.scalars(select(Partner).where(Partner.active.is_(True), Partner.webhook_url.is_not(None)))
        return [_partner_dict(p, secret=True) for p in rows]
