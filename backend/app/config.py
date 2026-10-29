import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    base_url: str
    model: str
    prompt_version: str
    timeout_seconds: float

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or DEFAULT_ENV_FILE, override=False)

        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        model = os.getenv("DEEPSEEK_MODEL", "").strip()
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        if not model:
            raise ValueError("DEEPSEEK_MODEL is required")

        timeout_value = os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30").strip()
        try:
            timeout_seconds = float(timeout_value)
        except ValueError:
            raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be numeric") from None
        if timeout_seconds <= 0:
            raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be positive")

        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ).rstrip("/"),
            model=model,
            prompt_version=os.getenv("DEEPSEEK_PROMPT_VERSION", "v1").strip(),
            timeout_seconds=timeout_seconds,
        )
