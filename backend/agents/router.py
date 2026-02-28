import json
from typing import Any, Dict

import httpx

from .. import config
from .types import RouterResult

_ROUTER_SYSTEM = (
    "You are a router for a release intelligence assistant. "
    "Given a single user question, you must output a small JSON object with keys: "
    "`type` (one of: patch, latest_version, version_on_date, unknown), "
    "`vendor_hint` (string or null; use \"linux\" when the question is about Linux), "
    "`date_hint` (string in YYYY-MM-DD format or null). "
    "Do not include any other keys. Do not answer the question. Output only valid JSON."
)

_FALLBACK = {
    "type": "patch",
    "vendor_hint": None,
    "date_hint": None,
}


async def _call_gemini_router(prompt: str) -> Dict[str, Any]:
    """Call Google Gemini API for router (classify question, extract hints)."""
    api_key = config.SETTINGS.gemini_api_key
    if not api_key:
        return _FALLBACK

    model = config.SETTINGS.gemini_model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": _ROUTER_SYSTEM}]},
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=body)
            if resp.status_code in (429, 500, 502, 503):
                return _FALLBACK
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, Exception):
        return _FALLBACK

    try:
        candidates = data.get("candidates") or []
        if not candidates:
            return _FALLBACK
        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            return _FALLBACK
        text = parts[0].get("text", "").strip()
        if not text:
            return _FALLBACK
        return json.loads(text)
    except (KeyError, json.JSONDecodeError):
        return _FALLBACK


async def route_question(question: str) -> RouterResult:
    """
    Main entrypoint used by the FastAPI app.
    For Linux questions: force type=patch and vendor_hint=linux.
    """
    raw = await _call_gemini_router(question)
    q = (question or "").lower()

    if "linux" in q:
        rtype = "patch"
        vendor_hint = "linux"
    else:
        rtype = raw.get("type") if raw.get("type") in {
            "patch",
            "latest_version",
            "version_on_date",
            "unknown",
        } else "patch"
        vendor_hint = raw.get("vendor_hint")
        if isinstance(vendor_hint, str):
            vendor_hint = vendor_hint.strip() or None
        else:
            vendor_hint = None

    date_hint = raw.get("date_hint")
    if isinstance(date_hint, str):
        date_hint = date_hint.strip() or None
    else:
        date_hint = None

    return RouterResult(
        type=rtype,
        vendor_hint=vendor_hint,
        date_hint=date_hint,
        raw_llm_output=raw,
    )

