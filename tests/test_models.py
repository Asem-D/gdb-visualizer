"""
Tests for gdbviz.models — Graph, Node, Edge data models.

These tests run without arcpy or GDAL (pure Python).
"""

import json
import pytest
from gdbviz.models import (
    Graph, Node, Edge,
    NodeType, EdgeType, GeometryType, FieldType, DomainType, Cardinality,
    Field, Subtype, Domain, RelationshipClass, Topology, TopologyRule,
    LARGE_SCHEMA_THRESHOLD, HUGE_SCHEMA_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    graph = Graph(name="TestGDB", path="C:\\Data\\Test.gdb")

    # Feature dataset
    graph.add_node(Node(
        id="feature_dataset://Infrastructure",
        name="Infrastructure",
        node_type=NodeType.FEATURE_DATASET,
        properties={"spatial_reference": "WGS_1984_UTM_Zone_37N"},
    ))

    # Feature classes
    graph.add_node(Node(
        id="feature_class://Test.gdb\\Infrastructure\\Roads",
        name="Roads",
        node_type=NodeType.FEATURE_CLASS,
        properties={
            "geometry_type": "Polyline",
            "field_count": 5,
            "feature_dataset": "Infrastructure",
        },
    ))

    graph.add_node(Node(
        id="feature_class://Test.gdb\\Infrastructure\\Bridges",
        name="Bridges",
        node_type=NodeType.FEATURE_CLASS,
        properties={"geometry_type": "Point", "field_count": 4},
    ))

    # Table
    graph.add_node(Node(
        id="table://Test.gdb\\MaintenanceLog",
        name="MaintenanceLog",
        node_type=NodeType.TABLE,
        properties={"field_count": 6},
    ))

    # Domains
    graph.add_node(Node(
        id="domain://RoadClassDomain",
        name="RoadClassDomain",
        node_type=NodeType.DOMAIN,
        properties={"domain_type": "codedValue", "coded_values": {1: "Highway", 2: "Local"}},
    ))

    # Edges
    graph.add_edge(Edge(
        source="feature_dataset://Infrastructure",
        target="feature_class://Test.gdb\\Infrastructure\\Roads",
        edge_type=EdgeType.CONTAINS,
        label="contains",
    ))

    graph.add_edge(Edge(
        source="feature_dataset://Infrastructure",
        target="feature_class://Test.gdb\\Infrastructure\\Bridges",
        edge_type=EdgeType.CONTAINS,
        label="contains",
    ))

    graph.add_edge(Edge(
        source="feature_class://Test.gdb\\Infrastructure\\Roads",
        target="domain://RoadClassDomain",
        edge_type=EdgeType.USES_DOMAIN,
        label="RoadClass → RoadClassDomain",
    ))

    return graph


# ---------------------------------------------------------------------------
# Tests: Graph basics
# ---------------------------------------------------------------------------

class TestGraph:
    def test_empty_graph(self):
        graph = Graph(name="empty", path="/tmp/empty.gdb")
        assert graph.name == "empty"
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_add_node(self, sample_graph):
        assert len(sample_graph.nodes) == 5

    def test_add_node_idempotent(self, sample_graph):
        """Adding the same node twice should not duplicate it."""
        node = sample_graph.nodes[0]
        sample_graph.add_node(node)
        assert len(sample_graph.nodes) == 5  # no change

    def test_add_edge(self, sample_graph):
        assert len(sample_graph.edges) == 3

    def test_add_edge_idempotent(self, sample_graph):
        """Adding the same edge twice should not duplicate it."""
        edge = sample_graph.edges[0]
        sample_graph.add_edge(edge)
        assert len(sample_graph.edges) == 3  # no change

    def test_get_node(self, sample_graph):
        node = sample_graph.get_node("domain://RoadClassDomain")
        assert node is not None
        assert node.name == "RoadClassDomain"

    def test_get_node_missing(self, sample_graph):
        node = sample_graph.get_node("nonexistent")
        assert node is None

    def test_get_nodes_by_type(self, sample_graph):
        fcs = sample_graph.get_nodes_by_type(NodeType.FEATURE_CLASS)
        assert len(fcs) == 2
        names = {n.name for n in fcs}
        assert "Roads" in names
        assert "Bridges" in names

    def test_get_edges_from(self, sample_graph):
        edges = sample_graph.get_edges_from("feature_dataset://Infrastructure")
        assert len(edges) == 2

    def test_get_edges_to(self, sample_graph):
        edges = sample_graph.get_edges_to("domain://RoadClassDomain")
        assert len(edges) == 1

    def test_stats(self, sample_graph):
        stats = sample_graph.stats
        assert stats["total_nodes"] == 5
        assert stats["total_edges"] == 3
        assert stats["node_types"]["feature_dataset"] == 1
        assert stats["node_types"]["feature_class"] == 2


# ---------------------------------------------------------------------------
# Tests: Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_json_and_back(self, sample_graph):
        json_str = sample_graph.to_json()
        restored = Graph.from_json(json_str)
        assert restored.name == sample_graph.name
        assert len(restored.nodes) == len(sample_graph.nodes)
        assert len(restored.edges) == len(sample_graph.edges)

    def test_roundtrip_preserves_types(self, sample_graph):
        json_str = sample_graph.to_json()
        restored = Graph.from_json(json_str)
        for orig, rest in zip(sample_graph.nodes, restored.nodes):
            assert orig.node_type == rest.node_type

    def test_to_dict(self, sample_graph):
        d = sample_graph.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert "name" in d
        assert len(d["nodes"]) == 5

    def test_json_is_valid(self, sample_graph):
        json_str = sample_graph.to_json()
        parsed = json.loads(json_str)  # should not raise
        assert isinstance(parsed, dict)

    def test_from_dict(self, sample_graph):
        d = sample_graph.to_dict()
        restored = Graph.from_dict(d)
        assert restored.name == "TestGDB"


# ---------------------------------------------------------------------------
# Tests: Node and Edge
# ---------------------------------------------------------------------------

class TestNode:
    def test_to_dict(self):
        node = Node(id="test://1", name="TestNode", node_type=NodeType.TABLE)
        d = node.to_dict()
        assert d["id"] == "test://1"
        assert d["name"] == "TestNode"
        assert d["node_type"] == "table"

    def test_to_dict_with_properties(self):
        node = Node(
            id="fc://1",
            name="FC",
            node_type=NodeType.FEATURE_CLASS,
            properties={"geometry_type": "Polygon", "field_count": 10},
        )
        d = node.to_dict()
        assert d["properties"]["geometry_type"] == "Polygon"


class TestEdge:
    def test_to_dict(self):
        edge = Edge(
            source="a",
            target="b",
            edge_type=EdgeType.CONTAINS,
            label="contains",
        )
        d = edge.to_dict()
        assert d["source"] == "a"
        assert d["target"] == "b"
        assert d["edge_type"] == "contains"
        assert d["label"] == "contains"


# ---------------------------------------------------------------------------
# Tests: Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_node_type_values(self):
        assert NodeType.FEATURE_CLASS.value == "feature_class"
        assert NodeType.TABLE.value == "table"
        assert NodeType.DOMAIN.value == "domain"

    def test_edge_type_values(self):
        assert EdgeType.CONTAINS.value == "contains"
        assert EdgeType.RELATIONSHIP.value == "relationship"

    def test_geometry_type_values(self):
        assert GeometryType.POLYGON.value == "Polygon"
        assert GeometryType.POINT.value == "Point"

    def test_field_type_values(self):
        assert FieldType.TEXT.value == "String"
        assert FieldType.DOUBLE.value == "Double"


# ---------------------------------------------------------------------------
# Tests: Field model
# ---------------------------------------------------------------------------

class TestField:
    def test_to_dict(self):
        field = Field(name="RoadName", field_type=FieldType.TEXT, length=100)
        d = field.to_dict()
        assert d["name"] == "RoadName"
        assert d["field_type"] == "String"
        assert d["length"] == 100

    def test_defaults(self):
        field = Field(name="Test", field_type=FieldType.LONG)
        assert field.is_nullable is True
        assert field.is_required is False
        assert field.is_oid is False


# ---------------------------------------------------------------------------
# Tests: Sample schema fixture
# ---------------------------------------------------------------------------

class TestSampleSchema:
    """Tests using the full sample schema JSON."""

    @pytest.fixture
    def sample_path(self):
        import pathlib
        return pathlib.Path(__file__).parent.parent / "examples" / "sample_schema.json"

    def test_loads(self, sample_path):
        graph = Graph.from_json(sample_path.read_text(encoding="utf-8"))
        assert graph.name == "CityGIS_Sample"

    def test_node_count(self, sample_path):
        graph = Graph.from_json(sample_path.read_text(encoding="utf-8"))
        assert len(graph.nodes) == 15

    def test_edge_count(self, sample_path):
        graph = Graph.from_json(sample_path.read_text(encoding="utf-8"))
        assert len(graph.edges) == 14

    def test_has_all_types(self, sample_path):
        graph = Graph.from_json(sample_path.read_text(encoding="utf-8"))
        type_counts = graph.stats["node_types"]
        assert type_counts.get("feature_dataset", 0) == 3
        assert type_counts.get("feature_class", 0) == 6
        assert type_counts.get("table", 0) == 1
        assert type_counts.get("domain", 0) == 3
        assert type_counts.get("topology", 0) == 1
        assert type_counts.get("relationship_class", 0) == 1


# ---------------------------------------------------------------------------
# Tests: Schema size classification
# ---------------------------------------------------------------------------

class TestSchemaSize:
    """Tests for Graph.schema_size and is_visualization_recommended."""

    def _make_graph_with_n_nodes(self, n):
        graph = Graph(name="SizedGDB", path="C:\\Data\\Sized.gdb")
        for i in range(n):
            graph.add_node(Node(
                id=f"table://table_{i}",
                name=f"Table_{i}",
                node_type=NodeType.TABLE,
                properties={"field_count": 3},
            ))
        return graph

    def test_empty_graph_is_normal(self):
        graph = Graph(name="empty", path="/tmp/empty.gdb")
        assert graph.schema_size == "normal"
        assert graph.is_visualization_recommended is True

    def test_small_schema_is_normal(self):
        graph = self._make_graph_with_n_nodes(10)
        assert graph.schema_size == "normal"
        assert graph.is_visualization_recommended is True

    def test_exactly_at_large_threshold(self):
        graph = self._make_graph_with_n_nodes(LARGE_SCHEMA_THRESHOLD)
        assert graph.schema_size == "large"
        assert graph.is_visualization_recommended is False

    def test_just_below_large_threshold(self):
        graph = self._make_graph_with_n_nodes(LARGE_SCHEMA_THRESHOLD - 1)
        assert graph.schema_size == "normal"
        assert graph.is_visualization_recommended is True

    def test_exactly_at_huge_threshold(self):
        graph = self._make_graph_with_n_nodes(HUGE_SCHEMA_THRESHOLD)
        assert graph.schema_size == "huge"
        assert graph.is_visualization_recommended is False

    def test_just_below_huge_threshold(self):
        graph = self._make_graph_with_n_nodes(HUGE_SCHEMA_THRESHOLD - 1)
        assert graph.schema_size == "large"
        assert graph.is_visualization_recommended is False

    def test_well_above_huge_threshold(self):
        graph = self._make_graph_with_n_nodes(1000)
        assert graph.schema_size == "huge"
        assert graph.is_visualization_recommended is False
