import asyncio
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config
from .agents import router as router_agent
from .agents import vendor_date_gate
from .agents import verifier
from .agents import answer_composer
from .services import trace_store
from .services import data_layer_client
from .services import releasetrain_search_client
from .services import neo4j_client


app = FastAPI(title="ReleaseHub Agents Backend")

# Simple, permissive CORS for hackathon demo; tighten later if needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    query_id: str
    status: str
    answer: str
    vendor: Optional[str] = None
    date: Optional[str] = None
    verified_version: Optional[str] = None
    version: Optional[str] = None  # frontend display (same as verified_version when answered)
    source: Optional[str] = None  # e.g. "Release Hub"
    meta: Dict[str, Any] = {}
    evidence: Any = None
    coreEvidence: List[Any] = []
    extraEvidence: List[Any] = []


@app.get("/health")
async def health() -> Dict[str, str]:
    # Basic config sanity check
    return {"status": "ok", "environment": config.SETTINGS.environment}


def _model_to_dict(obj: Any) -> Dict[str, Any]:
    """Serialize Pydantic model to dict (v1 .dict() or v2 .model_dump())."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj)


@app.post("/answer", response_model=AnswerResponse)
async def answer(request: QuestionRequest) -> AnswerResponse:
    """
    Orchestrates the full agent pipeline for a single question.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    query_id = str(uuid.uuid4())
    trace = trace_store.Trace(query_id=query_id, question=request.question)

    try:
        # 1) Router agent (Gemini)
        router_result = await router_agent.route_question(request.question)
        trace.steps.append({"agent": "router", "output": _model_to_dict(router_result)})

        # 2) Vendor + date gate
        vendor_result = await vendor_date_gate.resolve_vendor_and_date(
            question=request.question,
            vendor_hint=router_result.vendor_hint,
            date_hint=router_result.date_hint,
        )
        trace.steps.append({"agent": "vendor_date_gate", "output": _model_to_dict(vendor_result)})

        if vendor_result.status == "abstain":
            abstain_answer = "I cannot answer because the vendor is not in the trusted allow-list."
            final = AnswerResponse(
                query_id=query_id,
                status="abstain",
                answer=abstain_answer,
                vendor=None,
                date=vendor_result.date,
                verified_version=None,
                version=None,
                source="Release Hub",
                meta={"reason": vendor_result.reason},
                evidence=None,
                coreEvidence=[],
                extraEvidence=[],
            )
            trace.final_response = _model_to_dict(final)
            trace_store.store_trace(trace)
            try:
                await asyncio.to_thread(
                    neo4j_client.write_explainability_graph,
                    query_id=query_id,
                    question=request.question,
                    status="abstain",
                    vendor=None,
                    version=None,
                    evidence_urls=None,
                )
            except Exception:
                pass
            return final

        # 3) Retriever: for "patch for Linux on <date>", only source is Releasetrain search API; no other criteria or fallback
        query_type = router_result.type if router_result.type in ("latest_version", "version_on_date", "patch") else "latest_version"
        fact = None
        if vendor_result.vendor == "linux" and vendor_result.date and query_type in ("version_on_date", "patch"):
            fact = await releasetrain_search_client.fetch_linux_patch_on_date(vendor_result.date)
            # No fallback: if no data in that source, abstain
        else:
            if vendor_result.date and query_type in ("version_on_date", "patch"):
                fact = await data_layer_client.fetch_fact_on_date(vendor_result.vendor, vendor_result.date)
            if fact is None:
                fact = await data_layer_client.fetch_latest_fact(vendor_result.vendor)

        trace.steps.append({"agent": "retriever", "output": {"fact_found": fact is not None}})

        # 4) Verifier (deterministic safety gate)
        if fact is None:
            verification = verifier.VerificationResult(
                status="abstain",
                verified_version=None,
                reason="NO_RECORD_FOUND",
                evidence_ids=[],
                vendor=vendor_result.vendor,
                date=vendor_result.date,
            )
        else:
            verification = verifier.verify_fact(fact)
        trace.steps.append({"agent": "verifier", "output": _model_to_dict(verification)})

        # 5) Answer composer
        final_answer_text = await answer_composer.compose_from_verification(
            question=request.question,
            verification=verification,
        )

        evidence_urls: List[str] = []
        if fact and fact.evidence:
            for e in fact.evidence:
                if e.url_or_id:
                    evidence_urls.append(e.url_or_id)

        final = AnswerResponse(
            query_id=query_id,
            status=verification.status,
            answer=final_answer_text,
            vendor=verification.vendor,
            date=verification.date,
            verified_version=verification.verified_version,
            version=verification.verified_version,
            source="Release Hub",
            meta={"reason": verification.reason},
            evidence=verification.evidence_ids,
            coreEvidence=[],
            extraEvidence=[],
        )
        trace.final_response = _model_to_dict(final)
        trace_store.store_trace(trace)

        # Neo4j: write explainability graph (sponsor integration, non-blocking)
        try:
            await asyncio.to_thread(
                neo4j_client.write_explainability_graph,
                query_id=query_id,
                question=request.question,
                status=verification.status,
                vendor=verification.vendor,
                version=verification.verified_version,
                evidence_urls=evidence_urls,
            )
        except Exception:
            pass

        return final

    except Exception as e:
        err_msg = str(e)
        final = AnswerResponse(
            query_id=query_id,
            status="error",
            answer=f"Backend error: {err_msg}",
            vendor=None,
            date=None,
            verified_version=None,
            version=None,
            source="Release Hub",
            meta={"error": err_msg},
            evidence=None,
            coreEvidence=[],
            extraEvidence=[],
        )
        trace.steps.append({"agent": "error", "output": {"message": err_msg}})
        trace.final_response = _model_to_dict(final)
        trace_store.store_trace(trace)
        return final


@app.get("/trace/{query_id}")
async def get_trace(query_id: str) -> Dict[str, Any]:
    trace = trace_store.get_trace(query_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    out = trace.dict()
    if trace.final_response and isinstance(trace.final_response, dict):
        out["final_response"] = trace.final_response
    return out

