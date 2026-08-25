"""
BlockSync Railway Network Graph Builder.

Place at: backend/graph/network_builder.py

Builds a NetworkX graph from the existing Section table -- no new DB
tables required. Station nodes are derived from the distinct
from_station/to_station values already on Section; a station becomes a
"junction" purely from its degree (how many sections touch it), which
falls naturally out of the multi-train ingestion in load_data.py.

This module is READ-ONLY with respect to the optimizer/constraint
pipeline: it queries Section, Defect, BlockRequest but never writes to
them, so it can't affect Plan A/B/C generation.

Exposes one function, build_network(db), used by graph_routes.py.
"""

import networkx as nx
from models import Section, Defect, BlockRequest


def _section_status(open_defect_count, pending_request_count):
    """Simple, explainable status derivation for the frontend to color
    an edge by -- deliberately not ML, same philosophy as the
    constraint engine: must be defensible under questioning."""
    if open_defect_count >= 3:
        return "critical"
    if open_defect_count >= 1 or pending_request_count >= 1:
        return "attention"
    return "normal"


def build_network(db):
    """Builds the graph and returns a plain-dict payload ready for JSON:
        {
          "nodes": [{id, label, is_junction, degree}, ...],
          "edges": [{id, section_id, source, target, distance_km,
                      traffic_density, open_defects, pending_requests,
                      status}, ...],
          "stats": {section_count, station_count, junction_count}
        }
    """
    sections = db.query(Section).all()

    G = nx.Graph()

    # pre-aggregate defect / block-request counts per section so we
    # don't run a query per edge
    from sqlalchemy import func

    defect_counts = dict(
        db.query(Defect.section_id, func.count(Defect.id))
        .filter(Defect.status == "Open")
        .group_by(Defect.section_id)
        .all()
    )
    request_counts = dict(
        db.query(BlockRequest.section_id, func.count(BlockRequest.id))
        .filter(BlockRequest.status == "Pending")
        .group_by(BlockRequest.section_id)
        .all()
    )

    for s in sections:
        G.add_edge(
            s.from_station,
            s.to_station,
            section_id=s.section_id,
            db_id=s.id,
            distance_km=s.distance_km,
            traffic_density=s.traffic_density,
            open_defects=defect_counts.get(s.id, 0),
            pending_requests=request_counts.get(s.id, 0),
        )

    nodes = []
    for station in G.nodes():
        degree = G.degree(station)
        nodes.append({
            "id": station,
            "label": station,
            "is_junction": degree >= 3,
            "degree": degree,
        })

    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            "id": data["section_id"],
            "section_id": data["db_id"],
            "source": u,
            "target": v,
            "distance_km": data["distance_km"],
            "traffic_density": data["traffic_density"],
            "open_defects": data["open_defects"],
            "pending_requests": data["pending_requests"],
            "status": _section_status(data["open_defects"], data["pending_requests"]),
        })

    junction_count = sum(1 for n in nodes if n["is_junction"])

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "section_count": len(edges),
            "station_count": len(nodes),
            "junction_count": junction_count,
        },
    }
