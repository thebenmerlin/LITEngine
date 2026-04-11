"""
Argument graph builder — pure Python dict construction from a StructuredCaseProfile.

Produces a dict with "nodes" and "edges" suitable for frontend visualization.
No external graph libraries required.
"""

from typing import Any, Dict, List, Optional

from models.schemas import GraphEdge, GraphNode, SearchResult, StructuredCaseProfile
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Node type metadata
# ---------------------------------------------------------------------------

NODE_META: Dict[str, Dict[str, str]] = {
    "CLAIM": {
        "color": "#1B2A4A",
        "shape": "rectangle",
    },
    "EVIDENCE": {
        "color": "#374151",
        "shape": "ellipse",
    },
    "STATUTE": {
        "color": "#065F46",
        "shape": "diamond",
    },
    "PRECEDENT": {
        "color": "#92400E",
        "shape": "hexagon",
    },
    "ISSUE": {
        "color": "#1E3A5F",
        "shape": "round-rectangle",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_id(prefix: str, label: str) -> str:
    """Create a deterministic slug-like id."""
    slug = label.lower().strip().replace(" ", "_").replace("/", "_")[:60]
    # Strip trailing underscores
    slug = slug.rstrip("_") or "node"
    return f"{prefix}:{slug}"


def _node(nid: str, label: str, node_type: str, description: str = "",
          weight: float = 0.5) -> Dict[str, Any]:
    meta = NODE_META.get(node_type, {})
    return {
        "id": nid,
        "label": label,
        "type": node_type,
        "color": meta.get("color", "#666666"),
        "shape": meta.get("shape", "rectangle"),
        "weight": weight,
        "description": description,
        "weak": False,
    }


def _edge(eid: str, source: str, target: str, label: str,
          edge_type: str, strength: float = 0.5) -> Dict[str, Any]:
    return {
        "id": eid,
        "source": source,
        "target": target,
        "label": label,
        "type": edge_type,
        "strength": strength,
    }


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_argument_graph(
    profile: StructuredCaseProfile,
    precedents: Optional[List[SearchResult]] = None,
) -> Dict[str, Any]:
    """
    Build an argument graph from a StructuredCaseProfile.

    Node types created:
      - ISSUE  — one per legal_issue
      - CLAIM  — one per party (petitioner claim, respondent claim)
      - STATUTE — one per ipc_section and one per act_referenced
      - EVIDENCE — one per key_fact
      - PRECEDENT — one per provided precedent (max 3)

    Edges:
      EVIDENCE  → CLAIM   (supports)
      STATUTE   → CLAIM   (supports | contradicts — depends on context)
      PRECEDENT → ISSUE   (cites)
      CLAIM     → ISSUE   (raises)
      STATUTE   → ISSUE   (raises)

    Weak point detection:
      Any CLAIM node with zero incoming "supports" edges from EVIDENCE
      is flagged with weak=true.
    """

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Track which CLAIM nodes receive EVIDENCE support
    claim_support_sources: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # 1. ISSUE nodes
    # ------------------------------------------------------------------
    for issue_text in (profile.legal_issues or []):
        if not issue_text:
            continue
        nid = _node_id("issue", issue_text)
        # Truncate label for readability
        label = issue_text[:80] + ("…" if len(issue_text) > 80 else "")
        nodes.append(_node(nid, label, "ISSUE",
                           description=issue_text,
                           weight=0.7))

    # ------------------------------------------------------------------
    # 2. CLAIM nodes — one per party
    # ------------------------------------------------------------------
    claim_node_ids: Dict[str, str] = {}  # party role → node_id

    for role, party_name in [
        ("petitioner", profile.parties.petitioner),
        ("respondent", profile.parties.respondent),
    ]:
        if not party_name:
            continue

        # Infer a basic claim from party role and case context
        if role == "petitioner":
            claim_label = f"{party_name} — {profile.case_type} claim"
            claim_desc = f"Claim asserted by the petitioner: {party_name}"
        else:
            claim_label = f"{party_name} — defense"
            claim_desc = f"Defense asserted by the respondent: {party_name}"

        # Use relief_sought as petitioner claim detail if available
        if role == "petitioner" and profile.relief_sought:
            claim_desc += f" | Relief: {profile.relief_sought[:120]}"

        nid = _node_id("claim", claim_label)
        claim_node_ids[role] = nid
        claim_support_sources[nid] = 0

        nodes.append(_node(nid, claim_label[:80], "CLAIM",
                           description=claim_desc,
                           weight=0.8))

        # CLAIM → ISSUE (raises)
        for issue_text in (profile.legal_issues or []):
            if not issue_text:
                continue
            issue_nid = _node_id("issue", issue_text)
            edges.append(_edge(
                f"edge_{nid}_raises_{issue_nid}",
                nid, issue_nid,
                label="raises",
                edge_type="raises",
                strength=0.7,
            ))

    # ------------------------------------------------------------------
    # 3. STATUTE nodes — IPC sections + acts
    # ------------------------------------------------------------------
    statute_ids: List[str] = []

    for section in (profile.ipc_sections or []):
        if not section:
            continue
        nid = _node_id("statute", section)
        statute_ids.append(nid)
        nodes.append(_node(nid, section, "STATUTE",
                           description=f"Statutory provision: {section}",
                           weight=0.85))

        # STATUTE → ISSUE (raises)
        for issue_text in (profile.legal_issues or []):
            if not issue_text:
                continue
            issue_nid = _node_id("issue", issue_text)
            # Check if the section keyword appears in the issue
            section_lower = section.lower()
            issue_lower = issue_text.lower()
            # Simple relevance check
            relevant = any(
                part in issue_lower
                for part in section_lower.split()
                if len(part) > 2
            )
            strength = 0.8 if relevant else 0.4
            edges.append(_edge(
                f"edge_{nid}_raises_{issue_nid}",
                nid, issue_nid,
                label="relates to" if relevant else "referenced",
                edge_type="raises",
                strength=strength,
            ))

        # STATUTE → CLAIM (supports or contradicts)
        # Default to supports; use context to decide
        for role, claim_nid in claim_node_ids.items():
            # In criminal cases, sections typically support prosecution (petitioner)
            # Defense may contradict — heuristic based on role
            edge_type = "supports"
            label = "supports"
            strength = 0.6

            edges.append(_edge(
                f"edge_{nid}_to_{claim_nid}",
                nid, claim_nid,
                label=label,
                edge_type=edge_type,
                strength=strength,
            ))

    for act in (profile.acts_referenced or []):
        if not act:
            continue
        nid = _node_id("act", act)
        statute_ids.append(nid)
        nodes.append(_node(nid, act, "STATUTE",
                           description=f"Act referenced: {act}",
                           weight=0.6))

        # STATUTE → CLAIM (supports)
        for role, claim_nid in claim_node_ids.items():
            edges.append(_edge(
                f"edge_{nid}_to_{claim_nid}",
                nid, claim_nid,
                label="cited by",
                edge_type="supports",
                strength=0.4,
            ))

    # ------------------------------------------------------------------
    # 4. EVIDENCE nodes — key facts
    # ------------------------------------------------------------------
    evidence_count = 0
    for fact in (profile.key_facts or []):
        if not fact:
            continue
        nid = _node_id("evidence", f"fact_{evidence_count}")
        evidence_count += 1
        label = fact[:80] + ("…" if len(fact) > 80 else "")
        nodes.append(_node(nid, label, "EVIDENCE",
                           description=fact,
                           weight=0.6))

        # EVIDENCE → CLAIM (supports)
        # Distribute evidence across claims — primary support to petitioner
        # in criminal/civil cases
        primary_claim = claim_node_ids.get("petitioner") or claim_node_ids.get("respondent")
        if primary_claim:
            edges.append(_edge(
                f"edge_{nid}_supports_{primary_claim}",
                nid, primary_claim,
                label="supports",
                edge_type="supports",
                strength=0.65,
            ))
            claim_support_sources[primary_claim] = (
                claim_support_sources.get(primary_claim, 0) + 1
            )
        # Secondary claim (respondent) gets weaker support
        secondary_claim = claim_node_ids.get("respondent") or claim_node_ids.get("petitioner")
        if secondary_claim and secondary_claim != primary_claim:
            edges.append(_edge(
                f"edge_{nid}_supports_{secondary_claim}",
                nid, secondary_claim,
                label="context for",
                edge_type="supports",
                strength=0.3,
            ))

    # ------------------------------------------------------------------
    # 5. PRECEDENT nodes (optional, max 3)
    # ------------------------------------------------------------------
    prec_list = (precedents or [])[:3]
    for prec in prec_list:
        nid = _node_id("precedent", prec.doc_id)
        label = prec.title[:80] + ("…" if len(prec.title) > 80 else "")
        desc_parts = [prec.title]
        if prec.court:
            desc_parts.append(prec.court)
        if prec.date:
            desc_parts.append(prec.date)
        desc = " | ".join(desc_parts)

        nodes.append(_node(nid, label, "PRECEDENT",
                           description=desc,
                           weight=prec.similarity_score if hasattr(prec, "similarity_score") and prec.similarity_score else 0.5))

        # PRECEDENT → ISSUE (cites)
        for issue_text in (profile.legal_issues or []):
            if not issue_text:
                continue
            issue_nid = _node_id("issue", issue_text)
            edges.append(_edge(
                f"edge_{nid}_cites_{issue_nid}",
                nid, issue_nid,
                label="cites",
                edge_type="cites",
                strength=0.5,
            ))

    # ------------------------------------------------------------------
    # 6. Weak point detection
    # ------------------------------------------------------------------
    # A CLAIM is weak if no EVIDENCE node supports it (statutes don't count)
    weak_nodes: List[str] = []
    evidence_node_ids = {n["id"] for n in nodes if n["type"] == "EVIDENCE"}

    for node in nodes:
        if node["type"] == "CLAIM":
            evidence_supports = sum(
                1 for e in edges
                if e["source"] in evidence_node_ids
                and e["target"] == node["id"]
                and e["type"] == "supports"
            )
            if evidence_supports == 0:
                node["weak"] = True
                weak_nodes.append(node["id"])

    # ------------------------------------------------------------------
    # Build response
    # ------------------------------------------------------------------
    graph_nodes = [GraphNode(**n) for n in nodes]
    graph_edges = [GraphEdge(**e) for e in edges]

    logger.info(
        f"Built argument graph: {len(graph_nodes)} nodes, "
        f"{len(graph_edges)} edges, {len(weak_nodes)} weak claims"
    )

    return {
        "nodes": graph_nodes,
        "edges": graph_edges,
        "weak_nodes": weak_nodes,
        "node_count": len(graph_nodes),
        "edge_count": len(graph_edges),
    }
