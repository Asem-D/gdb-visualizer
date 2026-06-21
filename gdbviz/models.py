"""
Core data models for geodatabase schema representation.

These models are serialization-agnostic and serve as the canonical
intermediate representation between extractors and exporters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    """Types of schema elements that appear as graph nodes."""
    FEATURE_DATASET = "feature_dataset"
    FEATURE_CLASS = "feature_class"
    TABLE = "table"
    DOMAIN = "domain"
    TOPOLOGY = "topology"
    NETWORK = "network"
    RELATIONSHIP_CLASS = "relationship_class"
    ATTRIBUTE_RULE = "attribute_rule"


class EdgeType(str, Enum):
    """Types of relationships between schema elements."""
    CONTAINS = "contains"              # FeatureDataset → FeatureClass/Table
    RELATIONSHIP = "relationship"      # FC/Table ↔ FC/Table via RelationshipClass
    USES_DOMAIN = "uses_domain"        # Field → Domain
    TOPOLOGY_RULE = "topology_rule"    # Topology → FeatureClass
    HAS_SUBTYPES = "has_subtypes"      # FeatureClass → Subtype codes
    CONTROLLER = "controller"          # FeatureDataset → Topology/Network
    HAS_FIELD = "has_field"            # FeatureClass/Table → Field (collapsed by default)


class GeometryType(str, Enum):
    """ArcGIS geometry types."""
    POINT = "Point"
    MULTIPOINT = "MultiPoint"
    POLYLINE = "Polyline"
    POLYGON = "Polygon"
    UNKNOWN = "Unknown"
    NONE = "None"  # Non-spatial tables


class FieldType(str, Enum):
    """ArcGIS field data types."""
    SHORT = "SmallInteger"
    LONG = "Integer"
    FLOAT = "Single"
    DOUBLE = "Double"
    TEXT = "String"
    DATE = "Date"
    BLOB = "BLOB"
    RASTER = "Raster"
    GUID = "GUID"
    SHAPE = "Geometry"
    OID = "OID"


class DomainType(str, Enum):
    """Geodatabase domain types."""
    CODED_VALUE = "codedValue"
    RANGE = "range"


class Cardinality(str, Enum):
    """Relationship class cardinality."""
    ONE_TO_ONE = "OneToOne"
    ONE_TO_MANY = "OneToMany"
    MANY_TO_MANY = "ManyToMany"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Field:
    """A single field (column) in a feature class or table."""
    name: str
    field_type: FieldType
    alias: str = ""
    length: int | None = None
    is_nullable: bool = True
    is_required: bool = False
    default_value: Any = None
    domain: str = ""
    is_oid: bool = False
    is_shape: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["field_type"] = self.field_type.value
        return d


@dataclass
class Subtype:
    """A subtype code within a feature class."""
    code: int
    name: str
    default_value: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Domain:
    """A geodatabase domain (coded value or range)."""
    name: str
    domain_type: DomainType
    description: str = ""
    coded_values: dict[int, str] = field(default_factory=dict)
    min_value: float | None = None
    max_value: float | None = None
    field_type: FieldType = FieldType.TEXT

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "domain_type": self.domain_type.value,
            "description": self.description,
            "field_type": self.field_type.value,
        }
        if self.domain_type == DomainType.CODED_VALUE:
            d["coded_values"] = self.coded_values
        else:
            d["min_value"] = self.min_value
            d["max_value"] = self.max_value
        return d


@dataclass
class RelationshipClass:
    """A geodatabase relationship class."""
    name: str
    origin: str           # catalog path of origin class
    destination: str      # catalog path of destination class
    cardinality: Cardinality = Cardinality.ONE_TO_MANY
    forward_label: str = ""
    backward_label: str = ""
    origin_primary_key: str = ""
    destination_foreign_key: str = ""
    is_composite: bool = False
    notification: str = ""  # Forward, Backward, Both, None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cardinality"] = self.cardinality.value
        return d


@dataclass
class TopologyRule:
    """A single rule within a topology."""
    rule_type: str
    origin_feature_class: str
    destination_feature_class: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Topology:
    """A geodatabase topology."""
    name: str
    catalog_path: str = ""
    feature_dataset: str = ""
    tolerance: float = 0.001
    rules: list[TopologyRule] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "catalog_path": self.catalog_path,
            "feature_dataset": self.feature_dataset,
            "tolerance": self.tolerance,
            "rules": [r.to_dict() for r in self.rules],
        }


@dataclass
class Node:
    """A single node in the schema graph."""
    id: str                          # unique identifier (catalog path)
    name: str                        # display name
    node_type: NodeType
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "properties": self.properties,
        }


@dataclass
class Edge:
    """A single edge (relationship) in the schema graph."""
    source: str      # source node id
    target: str      # target node id
    edge_type: EdgeType
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type.value,
            "label": self.label,
            "properties": self.properties,
        }


# ---------------------------------------------------------------------------
# Schema size thresholds
# ---------------------------------------------------------------------------

LARGE_SCHEMA_THRESHOLD = 150   # nodes — diagrams become cluttered
HUGE_SCHEMA_THRESHOLD = 400    # nodes — diagrams become unusable


@dataclass
class Graph:
    """
    Complete schema graph — the canonical output of an extraction.

    This is the serializable intermediate representation that exporters
    consume. Extractors produce this; exporters render it.
    """
    name: str                        # geodatabase name
    path: str                        # geodatabase path
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- Convenience --------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """Add a node if not already present (idempotent)."""
        if not any(n.id == node.id for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        """Add an edge if not already present (source+target+type unique)."""
        key = (edge.source, edge.target, edge.edge_type)
        existing = {(e.source, e.target, e.edge_type) for e in self.edges}
        if key not in existing:
            self.edges.append(edge)

    def get_node(self, node_id: str) -> Node | None:
        """Look up a node by id."""
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_nodes_by_type(self, node_type: NodeType) -> list[Node]:
        """Return all nodes of a given type."""
        return [n for n in self.nodes if n.node_type == node_type]

    def get_edges_from(self, node_id: str) -> list[Edge]:
        """Return all outgoing edges from a node."""
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> list[Edge]:
        """Return all incoming edges to a node."""
        return [e for e in self.edges if e.target == node_id]

    @property
    def stats(self) -> dict[str, int]:
        """Quick summary counts."""
        type_counts = {}
        for n in self.nodes:
            t = n.node_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        edge_counts = {}
        for e in self.edges:
            t = e.edge_type.value
            edge_counts[t] = edge_counts.get(t, 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "edge_types": edge_counts,
        }

    @property
    def schema_size(self) -> str:
        """Classify schema size: 'normal', 'large', or 'huge'."""
        n = self.stats["total_nodes"]
        if n >= HUGE_SCHEMA_THRESHOLD:
            return "huge"
        elif n >= LARGE_SCHEMA_THRESHOLD:
            return "large"
        return "normal"

    @property
    def is_visualization_recommended(self) -> bool:
        """Whether interactive visualization is recommended for this schema."""
        return self.schema_size == "normal"

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "metadata": self.metadata,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> Graph:
        """Deserialize from a plain dictionary."""
        graph = cls(
            name=data["name"],
            path=data["path"],
            metadata=data.get("metadata", {}),
        )
        for nd in data.get("nodes", []):
            graph.nodes.append(Node(
                id=nd["id"],
                name=nd["name"],
                node_type=NodeType(nd["node_type"]),
                properties=nd.get("properties", {}),
            ))
        for ed in data.get("edges", []):
            graph.edges.append(Edge(
                source=ed["source"],
                target=ed["target"],
                edge_type=EdgeType(ed["edge_type"]),
                label=ed.get("label", ""),
                properties=ed.get("properties", {}),
            ))
        return graph

    @classmethod
    def from_json(cls, json_str: str) -> Graph:
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(json_str))
