"""
Neo4j client for explainability graph (sponsor integration).
Writes Query, Vendor, Release, Evidence nodes and relationships after each answer.
"""
from typing import Any, Dict, List, Optional


def write_explainability_graph(
    query_id: str,
    question: str,
    status: str,
    vendor: Optional[str] = None,
    version: Optional[str] = None,
    evidence_urls: Optional[List[str]] = None,
) -> None:
    """
    Write a minimal explainability graph to Neo4j: Query -> Vendor -> Release, Query -> Evidence.
    If NEO4J_URI is not set, no-op. Runs synchronously; call from asyncio.to_thread() if needed.
    """
    from .. import config

    uri = (config.SETTINGS.neo4j_uri or "").strip()
    user = (config.SETTINGS.neo4j_user or "").strip()
    password = (config.SETTINGS.neo4j_password or "").strip()
    if not uri or not user:
        return

    try:
        from neo4j import GraphDatabase
    except ImportError:
        return

    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Create or merge Query node
            session.run(
                """
                MERGE (q:Query {id: $query_id})
                SET q.question = $question, q.status = $status
                """,
                query_id=query_id,
                question=(question or "")[:1000],
                status=status or "unknown",
            )
            if vendor:
                session.run(
                    """
                    MERGE (v:Vendor {name: $name})
                    WITH v
                    MATCH (q:Query {id: $query_id})
                    MERGE (q)-[:ABOUT_VENDOR]->(v)
                    """,
                    name=vendor,
                    query_id=query_id,
                )
            if version and vendor:
                session.run(
                    """
                    MERGE (r:Release {vendor: $vendor, version: $version})
                    WITH r
                    MATCH (v:Vendor {name: $vendor})
                    MERGE (v)-[:HAS_RELEASE]->(r)
                    WITH r
                    MATCH (q:Query {id: $query_id})
                    MERGE (q)-[:ANSWERED_BY]->(r)
                    """,
                    vendor=vendor,
                    version=version,
                    query_id=query_id,
                )
            for url in (evidence_urls or [])[:10]:
                if not url:
                    continue
                session.run(
                    """
                    MERGE (e:Evidence {url: $url})
                    WITH e
                    MATCH (q:Query {id: $query_id})
                    MERGE (q)-[:EVIDENCE_USED]->(e)
                    """,
                    url=url[:500],
                    query_id=query_id,
                )
    except Exception:
        pass
    finally:
        if driver:
            try:
                driver.close()
            except Exception:
                pass
