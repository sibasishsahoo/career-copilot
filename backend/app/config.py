"""Application configuration.

Every setting comes from an environment variable or from the backend/.env file.
Nothing secret is ever written in the source code.

pydantic-settings does the work: it looks at each field below, finds an
environment variable with the same name (case-insensitive), converts it to the
right type, and gives us one typed `Settings` object.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ folder - located relative to THIS file, so paths work no matter which
# folder you start the server from.
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

# Default database: a SQLite file next to the code (backend/career_copilot.db).
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'career_copilot.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # ignore variables in .env that we don't declare here
    )

    app_name: str = "AI Career Copilot API"

    # Where application-tracker data is stored (Phase 4). Any SQLAlchemy URL works.
    database_url: str = DEFAULT_DATABASE_URL

    # Knowledge base / RAG (Phase 6)
    rag_store: str = "chroma"  # "chroma" = saved on disk, "memory" = lost when the server stops
    rag_embedder: str = "local"  # "local" = real model (needs a one-time download), "hashing" = word overlap only
    chroma_path: str = (BACKEND_DIR / "chroma_data").as_posix()
    rag_chunk_size: int = 800  # characters of new text per chunk
    rag_chunk_overlap: int = 150  # characters repeated from the previous chunk
    rag_min_score: float | None = None  # None = use the embedder's own default (see Embedder.default_min_score)

    # Agent (Phase 7)
    agent_max_steps: int = 4  # each step is one LLM call; the loop caps this at 10 whatever you set

    # Interview preparation (Phase 9)
    interview_question_count: int = 8  # questions per prep pack (3 to 12); every pack costs 2 LLM calls

    # Which provider the app uses: "gemini", "anthropic" or "openai"
    llm_provider: str = "gemini"

    # Gemini (default)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash-lite"

    # Anthropic (optional, for later)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # OpenAI (optional, for later)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    @property
    def llm_is_configured(self) -> bool:
        """True if the selected provider has a non-blank API key.

        Used by /health so you can see a missing key without making an LLM call.
        It never exposes the key itself.
        """
        keys = {
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
        }
        key = keys.get(self.llm_provider.strip().lower())
        return bool(key and key.strip())


@lru_cache
def get_settings() -> Settings:
    """Create the Settings object once and reuse it (reading .env every request is wasteful)."""
    return Settings()
