import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
def _csv(name: str, default: str) -> list[str]:
    return [m.strip() for m in os.getenv(name, default).split(",") if m.strip()]


# Free-tier quotas are per model, so when one model is rate-limited we try the next one.
GEMINI_FALLBACK_MODELS = _csv("GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite,gemini-3.5-flash-lite")
GROQ_FALLBACK_MODELS = _csv("GROQ_FALLBACK_MODELS", "openai/gpt-oss-20b,qwen/qwen3.8-27b")
# Protect the free tiers when many people check at once: at most N model calls in flight, the rest wait in line.
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "4"))
QUEUE_WAIT_SECONDS = float(os.getenv("QUEUE_WAIT_SECONDS", "25"))     # waiting longer than this = "busy"
CHAIN_BUDGET_SECONDS = float(os.getenv("CHAIN_BUDGET_SECONDS", "30"))  # stop trying more models after this long
DOMAIN_AGE_TIMEOUT = float(os.getenv("DOMAIN_AGE_TIMEOUT", "2.0"))
ANALYZER_PROVIDER = os.getenv("ANALYZER_PROVIDER", "groq")
ATTACKER_PROVIDER = os.getenv("ATTACKER_PROVIDER", "groq")
ATTACKER_MODEL = os.getenv("ATTACKER_MODEL", "")  # optional: a different model than the analyzer
CALL_DELAY_SECONDS = float(os.getenv("CALL_DELAY_SECONDS", "4"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Browsers allowed to call the API: localhost for development + the Vercel site (exact origins, plus *.vercel.app previews)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'unhook.db'}")

DOMAINS_PATH = ROOT / "config" / "official_domains.yaml"
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
CACHE_PATH = ROOT / ".cache" / "llm_cache.sqlite"
