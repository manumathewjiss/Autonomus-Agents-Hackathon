from .types import VerificationResult


async def compose_from_verification(
    question: str,
    verification: VerificationResult,
) -> str:
    """
    For now, keep this simple and deterministic:
    - If status is abstain: return a fixed abstain message with reason.
    - If status is answer: return a short template that includes the verified version.

    Once the rest of the pipeline is wired up, this function can call OpenAI
    to format the answer more nicely while enforcing that the verified
    version string appears verbatim in the output.
    """
    if verification.status == "abstain":
        reason = verification.reason or "insufficient trusted data"
        return f"I don't know from the current evidence ({reason})."

    if not verification.verified_version:
        return "I don't know from the current evidence (no verified version)."

    # For patch-on-date (e.g. "What is the patch for Linux on 2026-02-14?"): output only the slice value (e.g. "1.2.3")
    if verification.date:
        return verification.verified_version

    vendor_part = f" for {verification.vendor}" if verification.vendor else ""
    return f"The latest verified version{vendor_part} is {verification.verified_version}."

