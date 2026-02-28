"""
Single source for "patch for Linux on <date>" queries:
  https://releasetrain.io/api/v/search?q=linux&channel=patch&limit=25&page=1

Checking criteria only (all must match):
  - vendor: Linux (versionProductBrand or versionProductName)
  - date: YYYY-MM-DD (matched to versionReleaseDate, e.g. 20260214)
  - type: patch (versionReleaseChannel == "patch")

Output: only the slice — last value of versionSearchTags (e.g. ["linux","patch","20260214","1.2.3"] → "1.2.3").
If no matching record in this source, return None (caller abstains). No other criteria or fallback.
"""
import re
from typing import Any, Dict, List, Optional

import httpx

from ..agents.types import EvidenceItem, Fact


RELEASETRAIN_SEARCH_URL = "https://releasetrain.io/api/v/search?q=linux&channel=patch&limit=25&page=1"


def _normalize_date_to_yyyymmdd(date_str: Optional[str]) -> Optional[str]:
    """Convert YYYY-MM-DD to YYYYMMDD for comparison with versionReleaseDate."""
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    if re.match(r"^20\d{6}$", date_str):
        return date_str
    m = re.match(r"(20\d{2})-([01]\d)-([0-3]\d)", date_str)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    return None


def _date_yyyymmdd_to_dash(date_yyyymmdd: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD for output."""
    if len(date_yyyymmdd) == 8:
        return f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    return date_yyyymmdd


def _version_from_record(record: Dict[str, Any]) -> Optional[str]:
    """Output only the slice: last value of versionSearchTags (e.g. 1.2.3). No fallback."""
    tags = record.get("versionSearchTags")
    if isinstance(tags, list) and len(tags) > 0:
        return str(tags[-1]).strip()
    return None


def _record_matches_criteria(
    record: Dict[str, Any],
    date_yyyymmdd: str,
) -> bool:
    """True if record matches: vendor=Linux, date=YYYYMMDD, type=patch."""
    vendor = (record.get("versionProductBrand") or record.get("versionProductName") or "").strip()
    if vendor.lower() != "linux":
        return False
    if (record.get("versionReleaseChannel") or "").strip().lower() != "patch":
        return False
    release_date = record.get("versionReleaseDate")
    if not release_date:
        return False
    normalized = str(release_date).replace("-", "").replace(" ", "")
    return normalized == date_yyyymmdd


def _evidence_from_record(record: Dict[str, Any], vendor: str, version: Optional[str]) -> List[EvidenceItem]:
    """Build one EvidenceItem from a Releasetrain API record."""
    raw = record
    return [
        EvidenceItem(
            source="releasetrain",
            vendor=(raw.get("versionProductBrand") or raw.get("versionProductName") or vendor or "").strip(),
            observed_version=version,
            observed_at=raw.get("versionTimestampLastUpdate") or raw.get("versionReleaseDate"),
            url_or_id=raw.get("versionUrl"),
            raw_ref=raw,
            snippets=[raw.get("versionReleaseNotes")] if raw.get("versionReleaseNotes") else None,
        )
    ]


async def fetch_linux_patch_on_date(date_str: Optional[str]) -> Optional[Fact]:
    """
    Single source only: RELEASETRAIN_SEARCH_URL.
    Checking criteria (all required): vendor=Linux, date=YYYY-MM-DD, type=patch.
    Output version: only the slice — last value of versionSearchTags (e.g. "1.2.3").
    If no matching record in this source, return None (caller abstains).
    """
    date_yyyymmdd = _normalize_date_to_yyyymmdd(date_str)
    if not date_yyyymmdd:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(RELEASETRAIN_SEARCH_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    records = data.get("data") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    if not isinstance(records, list):
        return None

    matching = [r for r in records if isinstance(r, dict) and _record_matches_criteria(r, date_yyyymmdd)]
    if not matching:
        return None

    def sort_key(r):
        ts = r.get("versionTimestampLastUpdate") or r.get("versionTimestamp")
        if isinstance(ts, (int, float)):
            return ts
        if isinstance(ts, str):
            try:
                return int(float(ts))
            except ValueError:
                return 0
        return 0

    best = max(matching, key=sort_key)
    version = _version_from_record(best)
    if not version:
        return None

    evidence = _evidence_from_record(best, "Linux", version)
    as_of = best.get("versionReleaseDate") or best.get("versionTimestampLastUpdate")
    if as_of is not None:
        as_of = str(as_of)
    date_out = date_str if date_str and "-" in str(date_str) else _date_yyyymmdd_to_dash(date_yyyymmdd)

    return Fact(
        vendor="Linux",
        version=version,
        as_of=as_of,
        evidence=evidence,
        type="version_on_date",
        date_constraint=date_out,
    )
