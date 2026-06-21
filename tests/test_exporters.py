"""
Tests for gdbviz.exporter — JSON, Mermaid, PlantUML, DOT, Markdown exporters.

These tests run without arcpy or GDAL (pure Python, uses sample schema).
"""

import json
import pathlib
import pytest
from gdbviz.models import Graph, Node, Edge, NodeType, EdgeType
from gdbviz.exporter import (
    get_exporter, list_formats, JsonExporter, MermaidExporter,
    PlantUmlExporter, DotExporter, MarkdownExporter,
)


@pytest.fixture
def sample_graph():
    """Load the sample schema for export tests."""
    path = pathlib.Path(__file__).parent.parent / "examples" / "sample_schema.json"
    return Graph.from_json(path.read_text(encoding="utf-8"))


@pytest.fixture
def small_graph():
    """A minimal graph for quick tests."""
    g = Graph(name="Tiny", path="/tmp/tiny.gdb")
    g.add_node(Node(id="ds://main", name="Main", node_type=NodeType.FEATURE_DATASET))
    g.add_node(Node(id="fc://main\\Roads", name="Roads", node_type=NodeType.FEATURE_CLASS,
                    properties={"geometry_type": "Polyline", "field_count": 3}))
    g.add_node(Node(id="dom://RoadClass", name="RoadClass", node_type=NodeType.DOMAIN,
                    properties={"domain_type": "codedValue", "coded_values": {1: "High", 2: "Low"}}))
    g.add_edge(Edge(source="ds://main", target="fc://main\\Roads", edge_type=EdgeType.CONTAINS))
    g.add_edge(Edge(source="fc://main\\Roads", target="dom://RoadClass", edge_type=EdgeType.USES_DOMAIN))
    return g


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_list_formats(self):
        fmts = list_formats()
        assert "json" in fmts
        assert "mermaid" in fmts
        assert "plantuml" in fmts
        assert "dot" in fmts
        assert "markdown" in fmts

    def test_get_exporter_json(self):
        exp = get_exporter("json")
        assert isinstance(exp, JsonExporter)

    def test_get_exporter_mermaid(self):
        exp = get_exporter("mermaid")
        assert isinstance(exp, MermaidExporter)

    def test_get_exporter_unknown(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_exporter("nonexistent")


# ---------------------------------------------------------------------------
# JSON Exporter
# ---------------------------------------------------------------------------

class TestJsonExporter:
    def test_export_valid_json(self, sample_graph):
        exp = JsonExporter()
        output = exp.export(sample_graph)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_export_contains_nodes(self, sample_graph):
        exp = JsonExporter()
        output = exp.export(sample_graph)
        parsed = json.loads(output)
        assert len(parsed["nodes"]) == 15

    def test_export_file_extension(self):
        assert JsonExporter().file_extension == ".json"

    def test_roundtrip(self, small_graph):
        exp = JsonExporter()
        output = exp.export(small_graph)
        restored = Graph.from_json(output)
        assert len(restored.nodes) == 3
        assert len(restored.edges) == 2


# ---------------------------------------------------------------------------
# Mermaid Exporter
# ---------------------------------------------------------------------------

class TestMermaidExporter:
    def test_contains_graph_keyword(self, sample_graph):
        exp = MermaidExporter()
        output = exp.export(sample_graph)
        assert "graph LR" in output

    def test_contains_nodes(self, sample_graph):
        exp = MermaidExporter()
        output = exp.export(sample_graph)
        assert "Roads" in output
        assert "Bridges" in output

    def test_contains_edges(self, sample_graph):
        exp = MermaidExporter()
        output = exp.export(sample_graph)
        assert "-->" in output  # containment arrows

    def test_contains_styles(self, sample_graph):
        exp = MermaidExporter()
        output = exp.export(sample_graph)
        assert "classDef" in output

    def test_dashed_domain_edges(self, sample_graph):
        exp = MermaidExporter()
        output = exp.export(sample_graph)
        assert "-.->" in output  # dashed lines for domains

    def test_file_extension(self):
        assert MermaidExporter().file_extension == ".mmd"


# ---------------------------------------------------------------------------
# PlantUML Exporter
# ---------------------------------------------------------------------------

class TestPlantUmlExporter:
    def test_contains_start_end(self, sample_graph):
        exp = PlantUmlExporter()
        output = exp.export(sample_graph)
        assert "@startuml" in output
        assert "@enduml" in output

    def test_contains_packages(self, sample_graph):
        exp = PlantUmlExporter()
        output = exp.export(sample_graph)
        assert "package" in output

    def test_contains_classes(self, sample_graph):
        exp = PlantUmlExporter()
        output = exp.export(sample_graph)
        assert "class" in output

    def test_contains_enums(self, sample_graph):
        exp = PlantUmlExporter()
        output = exp.export(sample_graph)
        assert "enum" in output

    def test_file_extension(self):
        assert PlantUmlExporter().file_extension == ".puml"


# ---------------------------------------------------------------------------
# DOT Exporter
# ---------------------------------------------------------------------------

class TestDotExporter:
    def test_contains_digraph(self, sample_graph):
        exp = DotExporter()
        output = exp.export(sample_graph)
        assert "digraph" in output

    def test_contains_nodes(self, sample_graph):
        exp = DotExporter()
        output = exp.export(sample_graph)
        assert "Roads" in output

    def test_contains_arrows(self, sample_graph):
        exp = DotExporter()
        output = exp.export(sample_graph)
        assert "->" in output

    def test_domain_style(self, sample_graph):
        exp = DotExporter()
        output = exp.export(sample_graph)
        assert "style=dashed" in output  # domain edges

    def test_file_extension(self):
        assert DotExporter().file_extension == ".dot"


# ---------------------------------------------------------------------------
# Markdown Exporter
# ---------------------------------------------------------------------------

class TestMarkdownExporter:
    def test_contains_headers(self, sample_graph):
        exp = MarkdownExporter()
        output = exp.export(sample_graph)
        assert "# Schema:" in output
        assert "## Feature Classes" in output
        assert "## Tables" in output
        assert "## Domains" in output

    def test_contains_tables(self, sample_graph):
        exp = MarkdownExporter()
        output = exp.export(sample_graph)
        assert "| Name |" in output  # markdown table header

    def test_contains_stats(self, sample_graph):
        exp = MarkdownExporter()
        output = exp.export(sample_graph)
        assert "Summary" in output

    def test_file_extension(self):
        assert MarkdownExporter().file_extension == ".md"


# ---------------------------------------------------------------------------
# Export to file
# ---------------------------------------------------------------------------

class TestExportToFile:
    def test_json_export_to_file(self, small_graph, tmp_path):
        exp = JsonExporter()
        out_file = tmp_path / "test.json"
        result = exp.export_to_file(small_graph, out_file)
        assert result.exists()
        content = json.loads(result.read_text(encoding="utf-8"))
        assert len(content["nodes"]) == 3

    def test_mermaid_export_to_file(self, small_graph, tmp_path):
        exp = MermaidExporter()
        out_file = tmp_path / "test.mmd"
        result = exp.export_to_file(small_graph, out_file)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "graph LR" in content
