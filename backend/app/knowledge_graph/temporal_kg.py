from datetime import datetime
from typing import Any, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.enums import KGEdgeStatus
from app.domain.models import AtomicClaim, Contradiction, KGEdge, KGNode

logger = get_logger(__name__)


def _graph_props(obj) -> dict[str, Any]:
  """Extract properties from Neo4j Node/Relationship or plain dict."""
  if obj is None:
    return {}
  if isinstance(obj, dict):
    return obj
  if hasattr(obj, "_properties"):
    props = obj._properties
    return dict(props) if props else {}
  if hasattr(obj, "items"):
    try:
      return dict(obj.items())
    except (TypeError, AttributeError):
      pass
  return {}


def _node_id(props: dict[str, Any]) -> str:
  return str(props.get("entity_id") or props.get("name") or "")


def _node_entry(props: dict[str, Any]) -> dict[str, Any]:
  node_id = _node_id(props)
  return {
    "id": node_id,
    "name": props.get("name", node_id),
    "type": props.get("entity_type", "entity"),
  }


class TemporalKnowledgeGraph:
    """Neo4j-backed temporal knowledge graph with contradiction support."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            await self.connect()
        return self._driver  # type: ignore

    async def upsert_entity(self, node: KGNode) -> None:
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (e:Entity {entity_id: $entity_id})
                SET e.name = $name, e.entity_type = $entity_type
                """,
                entity_id=node.entity_id,
                name=node.name,
                entity_type=node.entity_type,
            )

    async def upsert_claim(self, claim: AtomicClaim) -> list[Contradiction]:
        """Store atomic claim as graph edge; detect contradictions without overwriting."""
        driver = await self._get_driver()
        contradictions: list[Contradiction] = []

        subject_id = self._entity_id(claim.subject)
        object_id = self._entity_id(claim.object)

        async with driver.session() as session:
            await session.run(
                """
                MERGE (s:Entity {entity_id: $subject_id})
                SET s.name = $subject_name
                """,
                subject_id=subject_id,
                subject_name=claim.subject,
            )
            await session.run(
                """
                MERGE (o:Entity {entity_id: $object_id})
                SET o.name = $object_name
                """,
                object_id=object_id,
                object_name=claim.object,
            )

            result = await session.run(
                """
                MATCH (s:Entity {entity_id: $subject_id})-[r:RELATES]->(o:Entity)
                WHERE r.predicate = $predicate AND r.status IN ['active', 'unresolved']
                RETURN r, o.entity_id AS target_id
                """,
                subject_id=subject_id,
                predicate=claim.predicate,
            )
            existing = await result.data()

            if existing:
                for record in existing:
                    edge_data = _graph_props(record["r"])
                    target_id = record.get("target_id", object_id)
                    existing_edge = KGEdge(
                        source_id=subject_id,
                        target_id=target_id,
                        relationship=claim.predicate,
                        confidence=edge_data.get("confidence", 0.5),
                        status=KGEdgeStatus(edge_data.get("status", "active")),
                        claim_id=edge_data.get("claim_id"),
                    )
                    if edge_data.get("object_value") and edge_data["object_value"] != claim.object:
                        contradictions.append(
                            Contradiction(
                                existing_edge=existing_edge,
                                new_claim=claim,
                                conflict_type="value_mismatch",
                                status=KGEdgeStatus.UNRESOLVED,
                            )
                        )
                        await session.run(
                            """
                            MATCH (s:Entity {entity_id: $subject_id})-[r:RELATES]->(o:Entity)
                            WHERE r.predicate = $predicate AND id(r) = $rel_id
                            SET r.status = 'unresolved'
                            """,
                            subject_id=subject_id,
                            predicate=claim.predicate,
                            rel_id=record["r"].id,
                        )
                        continue

            status = KGEdgeStatus.UNRESOLVED.value if contradictions else KGEdgeStatus.ACTIVE.value
            source_credibility = (
                sum(ref.credibility for ref in claim.source_refs) / len(claim.source_refs)
                if claim.source_refs
                else 0.5
            )
            await session.run(
                """
                MATCH (s:Entity {entity_id: $subject_id})
                MATCH (o:Entity {entity_id: $object_id})
                MERGE (s)-[r:RELATES {claim_id: $claim_id}]->(o)
                SET r.predicate = $predicate,
                    r.object_value = $object_value,
                    r.valid_from = $valid_from,
                    r.confidence = $confidence,
                    r.source_credibility = $source_credibility,
                    r.status = $status,
                    r.evidence_refs = $evidence_refs,
                    r.updated_at = datetime()
                """,
                subject_id=subject_id,
                object_id=object_id,
                predicate=claim.predicate,
                object_value=claim.object,
                claim_id=str(claim.id),
                valid_from=claim.timestamp.isoformat() if claim.timestamp else None,
                confidence=claim.confidence,
                source_credibility=source_credibility,
                status=status,
                evidence_refs=[ref.source_id for ref in claim.source_refs],
            )

        logger.info("kg_upsert", claim_id=str(claim.id), contradictions=len(contradictions))
        return contradictions

    async def get_subgraph(self, entity_name: str, depth: int = 2) -> dict[str, Any]:
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($name)
                OPTIONAL MATCH (e)-[r:RELATES]-(connected:Entity)
                RETURN e, r, connected
                LIMIT 50
                """,
                name=entity_name,
            )
            records = await result.data()

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for record in records:
            e_props = _graph_props(record.get("e"))
            c_props = _graph_props(record.get("connected"))
            r = record.get("r")

            if e_props:
                eid = _node_id(e_props)
                if eid:
                    nodes[eid] = _node_entry(e_props)

            if c_props:
                cid = _node_id(c_props)
                if cid:
                    nodes[cid] = _node_entry(c_props)

            if r is not None:
                rel_props = _graph_props(r)
                # Use relationship endpoints when available
                if hasattr(r, "start_node") and hasattr(r, "end_node"):
                    start_props = _graph_props(r.start_node)
                    end_props = _graph_props(r.end_node)
                    source_id = _node_id(start_props)
                    target_id = _node_id(end_props)
                    if source_id:
                        nodes[source_id] = _node_entry(start_props)
                    if target_id:
                        nodes[target_id] = _node_entry(end_props)
                else:
                    source_id = _node_id(e_props)
                    target_id = _node_id(c_props)

                if source_id and target_id:
                    edges.append({
                        "source": source_id,
                        "target": target_id,
                        "relationship": str(rel_props.get("predicate", "RELATES")),
                        "confidence": float(rel_props.get("confidence", 0.5)),
                        "status": str(rel_props.get("status", "active")),
                    })

        return {"nodes": list(nodes.values()), "edges": edges}

    async def find_contradictions(self, claim: AtomicClaim) -> list[Contradiction]:
        driver = await self._get_driver()
        subject_id = self._entity_id(claim.subject)
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (s:Entity {entity_id: $subject_id})-[r:RELATES]->(o:Entity)
                WHERE r.status = 'unresolved'
                RETURN r, o.entity_id AS object_id
                """,
                subject_id=subject_id,
            )
            records = await result.data()

        contradictions = []
        for record in records:
            edge_data = _graph_props(record["r"])
            contradictions.append(
                Contradiction(
                    existing_edge=KGEdge(
                        source_id=subject_id,
                        target_id=record.get("object_id", ""),
                        relationship=edge_data.get("predicate", ""),
                        confidence=edge_data.get("confidence", 0.5),
                        status=KGEdgeStatus.UNRESOLVED,
                    ),
                    new_claim=claim,
                    conflict_type="unresolved_edge",
                )
            )
        return contradictions

    @staticmethod
    def _entity_id(name: str) -> str:
        return name.lower().strip().replace(" ", "_")
