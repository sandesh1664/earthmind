"""Project-generated illustrative geometry. No official boundary or real streets."""

import hashlib
import json
from uuid import UUID, uuid5

NAMESPACE = UUID("3f675c59-69f5-4ec7-a4be-376567e00202")
SLUG = "dubai-downtown-demo"
REGION_ID = uuid5(NAMESPACE, f"region:{SLUG}")
DATA_SOURCE_ID = uuid5(NAMESPACE, "source:synthetic-downtown-v1")
NETWORK_ID = uuid5(NAMESPACE, "network:synthetic-downtown-v1")
DEMAND_ID = uuid5(NAMESPACE, "demand:synthetic-contract-v1")
SCENARIO_ID = uuid5(NAMESPACE, "scenario:synthetic-contract-v1")
BOUNDARY = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [55.2685, 25.1900],
                [55.2805, 25.1900],
                [55.2805, 25.2000],
                [55.2685, 25.2000],
                [55.2685, 25.1900],
            ]
        ]
    ],
}
NODES = (
    ("n0", 55.2700, 25.1920),
    ("n1", 55.2740, 25.1920),
    ("n2", 55.2780, 25.1920),
    ("n3", 55.2700, 25.1980),
    ("n4", 55.2740, 25.1980),
    ("n5", 55.2780, 25.1980),
)
EDGES = (
    ("e0", "n0", "n1", True),
    ("e1", "n1", "n2", False),
    ("e2", "n3", "n4", False),
    ("e3", "n4", "n5", True),
    ("e4", "n0", "n3", False),
    ("e5", "n1", "n4", True),
    ("e6", "n2", "n5", False),
    ("e7", "n0", "n4", False),
)
SYNTHETIC_METADATA = {
    "is_synthetic": True,
    "provenance": "EARTHMIND project-generated M02 fixture",
    "boundary_policy": "Illustrative study boundary, not an official municipal boundary",
}
DEFAULT_SPEED_MPS = 8.0
ROAD_CLASS = "synthetic_local"
SIGNALIZED_NODE = "n1"
ONE_WAY_LANES = 1
TWO_WAY_LANES = 2
MANIFEST = {
    "boundary": BOUNDARY,
    "nodes": NODES,
    "edges": EDGES,
    "metadata": SYNTHETIC_METADATA,
    "attributes": {
        "speed_limit_mps": DEFAULT_SPEED_MPS,
        "road_class": ROAD_CLASS,
        "simulated_signalized_node": SIGNALIZED_NODE,
        "one_way_lanes": ONE_WAY_LANES,
        "two_way_lanes": TWO_WAY_LANES,
    },
}
CHECKSUM = hashlib.sha256(
    json.dumps(MANIFEST, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


def node_id(name: str) -> UUID:
    return uuid5(NAMESPACE, f"node:{name}")


def edge_id(name: str) -> UUID:
    return uuid5(NAMESPACE, f"edge:{name}")
