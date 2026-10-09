from typing import Literal

from pydantic import BaseModel, Field, computed_field

VerdictLabel = Literal["scam", "suspicious", "safe"]

# scheme code -> Azerbaijani label shown to users
SCHEME_AZ = {
    "fake_bonus": "Saxta bonus / uduş",
    "bank_impersonation": "Bank adından fişinq",
    "fake_job": "Saxta iş elanı",
    "delivery_scam": "Çatdırılma fırıldağı",
    "investment_scam": "İnvestisiya fırıldağı",
    "other": "Digər fırıldaq",
    "none": "Sxem aşkar edilmədi",
}
SCHEME_CODES = list(SCHEME_AZ)


class Link(BaseModel):
    url: str
    domain: str
    status: Literal["official", "lookalike", "suspicious", "shortener", "unknown"]
    flags: list[str] = Field(default_factory=list)
    age_days: int | None = None  # days since the domain was registered (live checks only; None = unknown)


class Verdict(BaseModel):
    verdict: VerdictLabel
    scheme: str  # one of SCHEME_CODES
    reasons: list[str]  # Azerbaijani
    actions: list[str]  # Azerbaijani
    confidence: float
    explanation_az: str = ""
    links: list[Link] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)  # masked
    text_redacted: str = ""  # redacted text (incl. screenshot transcript), the only text we store
    degraded: bool = False  # True when no LLM answered and we fell back to link checks
    provider: str = ""  # which LLM produced the verdict ("" when degraded)
    model: str = ""
    usage: list[dict] = Field(default_factory=list)  # one entry per model call: tokens, latency, provider, model

    @computed_field
    @property
    def scheme_az(self) -> str:
        return SCHEME_AZ.get(self.scheme, SCHEME_AZ["other"])
