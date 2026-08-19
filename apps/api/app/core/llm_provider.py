from app.core.config import Settings, get_settings

GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def is_gemini(settings: Settings | None = None) -> bool:
    current = settings or get_settings()
    key = current.llm_api_key.strip()
    return key.startswith("AQ.") or "generativelanguage.googleapis.com" in current.llm_base_url


def gemini_headers(settings: Settings | None = None) -> dict[str, str]:
    current = settings or get_settings()
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": current.llm_api_key.strip(),
    }


def gemini_model(name: str) -> str:
    return name.removeprefix("models/")
