import re
from typing import Optional

from .types import VendorDateResult


def _extract_date(question: str, date_hint: Optional[str]) -> Optional[str]:
    """Extract YYYY-MM-DD if present."""
    if date_hint:
        return date_hint
    m = re.search(r"(20[0-9]{2}-[01][0-9]-[0-3][0-9])", question)
    return m.group(1) if m else None


async def resolve_vendor_and_date(
    question: str,
    vendor_hint: Optional[str],
    date_hint: Optional[str],
) -> VendorDateResult:
    """
    Resolve vendor and date. Checking criteria only: vendor=Linux, date=YYYY-MM-DD (from question).
    Type=patch is set by router for Linux. All other checking criteria removed.
    """
    question_lower = (question or "").lower()

    if "linux" not in question_lower:
        return VendorDateResult(
            status="abstain",
            vendor=None,
            date=None,
            reason="UNKNOWN_VENDOR",
        )

    vendor = "linux"
    date = _extract_date(question, date_hint)
    return VendorDateResult(status="ok", vendor=vendor, date=date)

