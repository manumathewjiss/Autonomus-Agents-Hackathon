"""
Client for Far's data layer (Node service).
Calls GET /facts/latest and GET /facts/on-date and maps responses to our Fact + EvidenceItem types.
"""
from typing import Any, Dict, List, Optional

import httpx

from .. import config
from ..agents.types import EvidenceItem, Fact


def _evidence_from_payload(vendor: str, payload: Dict[str, Any]) -> List[EvidenceItem]:
    """Build one EvidenceItem from Node's buildAnswerPayload response."""
    raw = payload.get("raw") or {}
    main_data = payload.get("mainData")
    info = payload.get("additionalInformation") or {}
    return [
        EvidenceItem(
            source="releasetrain",
            vendor=(raw.get("versionProductBrand") or raw.get("versionProductName") or vendor or "").strip(),
            observed_version=str(main_data) if main_data is not None else None,
            observed_at=raw.get("versionTimestampLastUpdate") or raw.get("versionReleaseDate"),
            url_or_id=info.get("versionUrl") or raw.get("versionUrl"),
            raw_ref=raw,
            snippets=[info.get("versionReleaseNotes")] if info.get("versionReleaseNotes") else None,
        )
    ]


def _fact_from_payload(
    vendor: str,
    query_type: str,
    date_constraint: Optional[str],
    payload: Dict[str, Any],
) -> Fact:
    main_data = payload.get("mainData")
    version = str(main_data).strip() if main_data is not None else None
    raw = payload.get("raw") or {}
    as_of = raw.get("versionReleaseDate") or raw.get("versionTimestampLastUpdate")
    if as_of is not None:
        as_of = str(as_of)
    evidence = _evidence_from_payload(vendor, payload)
    return Fact(
        vendor=vendor,
        version=version,
        as_of=as_of,
        evidence=evidence,
        type=query_type,
        date_constraint=date_constraint,
    )


# Vendor aliases: Releasetrain may store under one name, user may ask with another.
# "os" alone often matches from "mac os"; allow-list may not have "mac os", so try macOS variants.
_VENDOR_ALIASES: Dict[str, List[str]] = {
    "macos": ["macos", "apple", "mac os"],
    "apple": ["apple", "macos", "mac os"],
    "mac os": ["mac os", "apple", "macos"],
    "os": ["mac os", "macos", "apple", "os"],
}


def _vendor_candidates(vendor: str) -> List[str]:
    """Return list of vendor strings to try (primary first, then aliases)."""
    v = (vendor or "").strip().lower()
    if not v:
        return []
    if v in _VENDOR_ALIASES:
        return _VENDOR_ALIASES[v]
    return [v]


async def fetch_latest_fact(vendor: str) -> Optional[Fact]:
    """
    Call Node service GET /facts/latest?vendor=...
    Tries vendor and known aliases (e.g. macos -> apple). Returns a Fact or None if 404 or request error.
    """
    base = config.SETTINGS.data_layer_service_url.rstrip("/")
    url = f"{base}/facts/latest"
    candidates = _vendor_candidates(vendor)
    if not candidates:
        candidates = [vendor]
    async with httpx.AsyncClient(timeout=15) as client:
        for v in candidates:
            try:
                resp = await client.get(url, params={"vendor": v})
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()
                return _fact_from_payload(vendor, "latest_version", None, data)
            except Exception:
                continue
    return None


async def fetch_fact_on_date(vendor: str, date: str) -> Optional[Fact]:
    """
    Call Node service GET /facts/on-date?vendor=...&date=YYYY-MM-DD
    Tries vendor and aliases. Returns a Fact or None if 404 or request error.
    """
    base = config.SETTINGS.data_layer_service_url.rstrip("/")
    url = f"{base}/facts/on-date"
    candidates = _vendor_candidates(vendor)
    if not candidates:
        candidates = [vendor]
    async with httpx.AsyncClient(timeout=15) as client:
        for v in candidates:
            try:
                resp = await client.get(url, params={"vendor": v, "date": date})
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()
                return _fact_from_payload(vendor, "version_on_date", date, data)
            except Exception:
                continue
    return None
