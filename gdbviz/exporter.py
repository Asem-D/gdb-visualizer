"""
Exporters — render a Graph to various output formats.

Supported formats:
- json      — primary interchange format (D3.js compatible)
- mermaid   — Mermaid.js flowchart diagrams
- plantuml  — PlantUML class/relationship diagrams
- dot       — Graphviz DOT language
- markdown  — Markdown table summary
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TextIO

from gdbviz.models import (
    Graph, Node, Edge,
    NodeType, EdgeType, GeometryType,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_exporters: dict[str, type[BaseExporter]] = {}


def register_exporter(cls: type[BaseExporter]) -> type[BaseExporter]:
    """Register an exporter by its format name."""
    _exporters[cls.format_name] = cls
    return cls


def get_exporter(format_name: str) -> BaseExporter:
    """Get an exporter instance by format name."""
    if format_name not in _exporters:
        available = list(_exporters.keys())
        raise ValueError(
            f"Unknown format '{format_name}'. Available: {available}"
        )
    return _exporters[format_name]()


def list_formats() -> list[str]:
    """List all registered export formats."""
    return list(_exporters.keys())


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseExporter(ABC):
    """Abstract base for graph exporters."""
    format_name: str = ""
    file_extension: str = ""
    content_type: str = "text/plain"

    @abstractmethod
    def export(self, graph: Graph) -> str:
        """Render the graph to a string."""
        ...

    def export_to_file(self, graph: Graph, path: str | Path) -> Path:
        """Render and write to a file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.export(graph)
        path.write_text(content, encoding="utf-8")
        return path

    def _sanitize_id(self, text: str) -> str:
        """Make a string safe for use as a diagram ID."""
        return (
            text.replace("\\", "/")
            .replace("-", "_")
            .replace(" ", "_")
            .replace(".", "_")
            .replace("/", "__")
            .replace(":", "_")
        )

    def _node_label(self, node: Node) -> str:
        """Generate a display label for a node."""
        type_icons = {
            NodeType.FEATURE_DATASET: "📁",
            NodeType.FEATURE_CLASS: "🔷",
            NodeType.TABLE: "📋",
            NodeType.DOMAIN: "🏷️",
            NodeType.TOPOLOGY: "🌐",
            NodeType.NETWORK: "🔗",
            NodeType.RELATIONSHIP_CLASS: "↔️",
            NodeType.ATTRIBUTE_RULE: "📏",
        }
        icon = type_icons.get(node.node_type, "❓")
        return f"{icon} {node.name}"

    def _edge_label(self, edge: Edge) -> str:
        """Generate a display label for an edge."""
        return edge.label or edge.edge_type.value


# ---------------------------------------------------------------------------
# JSON Exporter
# ---------------------------------------------------------------------------

@register_exporter
class JsonExporter(BaseExporter):
    """Export as JSON (primary interchange format, D3.js compatible)."""
    format_name = "json"
    file_extension = ".json"
    content_type = "application/json"

    def export(self, graph: Graph) -> str:
        return graph.to_json(indent=2)


# ---------------------------------------------------------------------------
# Mermaid Exporter
# ---------------------------------------------------------------------------

@register_exporter
class MermaidExporter(BaseExporter):
    """
    Export as Mermaid.js flowchart.

    Renders a readable diagram for GitHub READMEs, documentation,
    and the Mermaid Live Editor.
    """
    format_name = "mermaid"
    file_extension = ".mmd"
    content_type = "text/plain"

    # Node shape mappings
    SHAPES = {
        NodeType.FEATURE_DATASET: ("([", "])"),      # stadium/rounded
        NodeType.FEATURE_CLASS: ("[", "]"),            # rectangle
        NodeType.TABLE: ("[", "]"),                    # rectangle
        NodeType.DOMAIN: ("{", "}"),                   # diamond
        NodeType.TOPOLOGY: (">", "]"),                 # asymmetric
        NodeType.NETWORK: (">", "]"),                  # asymmetric
        NodeType.RELATIONSHIP_CLASS: (">>", "]"),      # subroutine
        NodeType.ATTRIBUTE_RULE: ("(", ")"),           # circle
    }

    # Styling classes
    STYLES = {
        NodeType.FEATURE_DATASET: "featureDataset",
        NodeType.FEATURE_CLASS: "featureClass",
        NodeType.TABLE: "tableNode",
        NodeType.DOMAIN: "domainNode",
        NodeType.TOPOLOGY: "topologyNode",
        NodeType.NETWORK: "networkNode",
        NodeType.RELATIONSHIP_CLASS: "relClassNode",
        NodeType.ATTRIBUTE_RULE: "attrRuleNode",
    }

    def export(self, graph: Graph) -> str:
        lines = ["graph LR", ""]

        # -- Style definitions ------------------------------------------------
        lines.append("    %% Node styles")
        lines.append("    classDef featureDataset fill:#9B59B6,stroke:#7D3C98,color:#fff")
        lines.append("    classDef featureClass fill:#4A90D9,stroke:#2E6BAC,color:#fff")
        lines.append("    classDef tableNode fill:#E8A838,stroke:#C08820,color:#fff")
        lines.append("    classDef domainNode fill:#50C878,stroke:#3DA55C,color:#fff")
        lines.append("    classDef topologyNode fill:#E85D5D,stroke:#C44040,color:#fff")
        lines.append("    classDef networkNode fill:#9B59B6,stroke:#7D3C98,color:#fff")
        lines.append("    classDef relClassNode fill:#6CB4EE,stroke:#4A90D9,color:#fff")
        lines.append("    classDef attrRuleNode fill:#B0B0B0,stroke:#888,color:#fff")
        lines.append("")

        # -- Node definitions -------------------------------------------------
        lines.append("    %% Nodes")
        node_ids = {}
        for node in graph.nodes:
            safe_id = self._sanitize_id(node.id)
            node_ids[node.id] = safe_id

            left, right = self.SHAPES.get(node.node_type, ("[", "]"))
            label = self._node_label(node)
            # Escape pipe characters for Mermaid
            label = label.replace("|", "\\|")
            lines.append(f"    {safe_id}{left}\"{label}\"{right}")

        lines.append("")

        # -- Edge definitions -------------------------------------------------
        lines.append("    %% Edges")
        for edge in graph.edges:
            src = node_ids.get(edge.source)
            tgt = node_ids.get(edge.target)
            if not src or not tgt:
                continue

            label = self._edge_label(edge)
            label = label.replace("|", "\\|")

            # Edge styling by type
            arrow = "-->"
            if edge.edge_type == EdgeType.USES_DOMAIN:
                arrow = "-.->"
            elif edge.edge_type == EdgeType.RELATIONSHIP:
                arrow = "<-->"

            lines.append(f"    {src} {arrow}|\"{label}\"| {tgt}")

        lines.append("")

        # -- Class assignments ------------------------------------------------
        lines.append("    %% Class assignments")
        for node in graph.nodes:
            safe_id = node_ids[node.id]
            style = self.STYLES.get(node.node_type, "")
            if style:
                lines.append(f"    class {safe_id} {style}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# PlantUML Exporter
# ---------------------------------------------------------------------------

@register_exporter
class PlantUmlExporter(BaseExporter):
    """
    Export as PlantUML class diagram.

    Renders a class/relationship diagram viewable in PlantUML editors,
    IntelliJ, VS Code (with PlantUML extension), or plantuml.com.
    """
    format_name = "plantuml"
    file_extension = ".puml"
    content_type = "text/plain"

    def export(self, graph: Graph) -> str:
        lines = [
            "@startuml GeodatabaseSchema",
            "",
            "' Theme",
            "skinparam linetype ortho",
            "skinparam backgroundColor #1E1E2E",
            "skinparam defaultFontColor #CDD6F4",
            "skinparam defaultFontSize 12",
            "",
            "skinparam class {",
            "  BackgroundColor #313244",
            "  BorderColor #89B4FA",
            "  FontColor #CDD6F4",
            "  HeaderBackgroundColor #45475A",
            "}",
            "",
            "skinparam package {",
            "  BackgroundColor #1E1E2E",
            "  BorderColor #89DCEB",
            "  FontColor #89DCEB",
            "}",
            "",
        ]

        # -- Feature datasets as packages ------------------------------------
        lines.append("' Feature Datasets (packages)")
        fd_nodes = graph.get_nodes_by_type(NodeType.FEATURE_DATASET)
        for fd in fd_nodes:
            safe_id = self._sanitize_id(fd.name)
            lines.append(f'package "{fd.name}" as {safe_id} {{')

            # Feature classes and tables inside this dataset
            contained_edges = [e for e in graph.edges
                               if e.source == fd.id and e.edge_type == EdgeType.CONTAINS]
            for ce in contained_edges:
                child = graph.get_node(ce.target)
                if child:
                    lines.append(f"  {self._class_declaration(child)}")

            lines.append("}")
            lines.append("")

        # -- Standalone tables (not in any dataset) --------------------------
        standalone_tables = []
        for node in graph.nodes:
            if node.node_type == NodeType.TABLE:
                # Check if it's contained in a dataset
                has_parent = any(
                    e.target == node.id and e.edge_type == EdgeType.CONTAINS
                    for e in graph.edges
                )
                if not has_parent:
                    standalone_tables.append(node)

        if standalone_tables:
            lines.append("' Standalone Tables")
            for tbl in standalone_tables:
                lines.append(self._class_declaration(tbl))
            lines.append("")

        # -- Domains as enums ------------------------------------------------
        domain_nodes = graph.get_nodes_by_type(NodeType.DOMAIN)
        if domain_nodes:
            lines.append("' Domains")
            for dom in domain_nodes:
                safe_id = self._sanitize_id(dom.name)
                dom_type = dom.properties.get("domain_type", "codedValue")
                lines.append(f'enum "{dom.name}" as {safe_id} {{')
                if dom_type == "codedValue":
                    coded = dom.properties.get("coded_values", {})
                    if isinstance(coded, dict):
                        for code, val in list(coded.items())[:15]:
                            lines.append(f"  {code} = {val}")
                    elif isinstance(coded, list):
                        for cv in coded[:15]:
                            if isinstance(cv, dict):
                                lines.append(f"  {cv.get('code', '?')} = {cv.get('name', '?')}")
                else:
                    min_v = dom.properties.get("min_value", "?")
                    max_v = dom.properties.get("max_value", "?")
                    lines.append(f"  {min_v} .. {max_v}")
                lines.append("}")
                lines.append("")

        # -- Topologies ------------------------------------------------------
        topo_nodes = graph.get_nodes_by_type(NodeType.TOPOLOGY)
        if topo_nodes:
            lines.append("' Topologies")
            for topo in topo_nodes:
                safe_id = self._sanitize_id(topo.name)
                rules = topo.properties.get("rules", [])
                lines.append(f'component "{topo.name}" as {safe_id} {{')
                for rule in rules[:10]:
                    rule_type = rule.get("rule_type", "rule")
                    origin = rule.get("origin", "")
                    lines.append(f"  {rule_type}: {origin}")
                lines.append("}")
                lines.append("")

        # -- Relationships ---------------------------------------------------
        rel_edges = [e for e in graph.edges if e.edge_type == EdgeType.RELATIONSHIP]
        if rel_edges:
            lines.append("' Relationship Classes")
            for edge in rel_edges:
                src_id = self._sanitize_id(edge.source.split("//")[-1])
                tgt_id = self._sanitize_id(edge.target.split("//")[-1])
                label = edge.label or ""
                lines.append(f'{src_id} --> {tgt_id} : {label}')
            lines.append("")

        # -- Domain usage (dashed lines) -------------------------------------
        domain_edges = [e for e in graph.edges if e.edge_type == EdgeType.USES_DOMAIN]
        if domain_edges:
            lines.append("' Domain assignments")
            for edge in domain_edges:
                src_id = self._sanitize_id(edge.source.split("//")[-1])
                tgt_id = self._sanitize_id(edge.target.split("//")[-1])
                lines.append(f'{src_id} ..> {tgt_id} : uses')
            lines.append("")

        # -- Topology rules --------------------------------------------------
        topo_edges = [e for e in graph.edges if e.edge_type == EdgeType.TOPOLOGY_RULE]
        if topo_edges:
            lines.append("' Topology rules")
            for edge in topo_edges:
                src_id = self._sanitize_id(edge.source.split("//")[-1])
                tgt_id = self._sanitize_id(edge.target.split("//")[-1])
                lines.append(f'{src_id} --> {tgt_id} : {edge.label}')
            lines.append("")

        lines.append("@enduml")
        return "\n".join(lines)

    def _class_declaration(self, node: Node) -> str:
        """Generate a PlantUML class declaration for a node."""
        safe_id = self._sanitize_id(node.name)
        stereotype = ""

        if node.node_type == NodeType.FEATURE_CLASS:
            geom = node.properties.get("geometry_type", "")
            stereotype = f" <<{geom}>>" if geom else ""
            fields = node.properties.get("fields", [])
            field_count = len(fields)
            return (
                f'class "{node.name}" as {safe_id}{stereotype} {{\n'
                f'  .. {field_count} fields ..\n'
                f'}}'
            )
        elif node.node_type == NodeType.TABLE:
            fields = node.properties.get("fields", [])
            field_count = len(fields)
            return (
                f'class "{node.name}" as {safe_id} {{\n'
                f'  .. {field_count} fields ..\n'
                f'}}'
            )
        else:
            return f'class "{node.name}" as {safe_id}'


# ---------------------------------------------------------------------------
# Graphviz DOT Exporter
# ---------------------------------------------------------------------------

@register_exporter
class DotExporter(BaseExporter):
    """
    Export as Graphviz DOT language.

    Render with: dot -Tpng schema.dot -o schema.png
    Or paste into https://dreampuf.github.io/GraphvizOnline/
    """
    format_name = "dot"
    file_extension = ".dot"
    content_type = "text/plain"

    # Node color mappings
    COLORS = {
        NodeType.FEATURE_DATASET: ("#9B59B6", "white"),
        NodeType.FEATURE_CLASS: ("#4A90D9", "white"),
        NodeType.TABLE: ("#E8A838", "white"),
        NodeType.DOMAIN: ("#50C878", "white"),
        NodeType.TOPOLOGY: ("#E85D5D", "white"),
        NodeType.NETWORK: ("#9B59B6", "white"),
        NodeType.RELATIONSHIP_CLASS: ("#6CB4EE", "white"),
        NodeType.ATTRIBUTE_RULE: ("#B0B0B0", "black"),
    }

    SHAPES = {
        NodeType.FEATURE_DATASET: "folder",
        NodeType.FEATURE_CLASS: "ellipse",
        NodeType.TABLE: "box",
        NodeType.DOMAIN: "diamond",
        NodeType.TOPOLOGY: "octagon",
        NodeType.NETWORK: "hexagon",
        NodeType.RELATIONSHIP_CLASS: "parallelogram",
        NodeType.ATTRIBUTE_RULE: "circle",
    }

    def export(self, graph: Graph) -> str:
        lines = [
            "digraph GeodatabaseSchema {",
            "    // Graph settings",
            "    rankdir=LR",
            "    bgcolor=\"#1E1E2E\"",
            "    fontname=\"Segoe UI\"",
            "    pad=0.5",
            "    nodesep=0.8",
            "    ranksep=1.2",
            "",
            "    // Default node style",
            "    node [fontname=\"Segoe UI\" fontsize=11 style=filled]",
            "    edge [fontname=\"Segoe UI\" fontsize=9 color=\"#888888\"]",
            "",
        ]

        # -- Nodes -----------------------------------------------------------
        lines.append("    // Nodes")
        for node in graph.nodes:
            safe_id = self._sanitize_id(node.id)
            label = self._node_label(node)
            bg, fg = self.COLORS.get(node.node_type, ("#666", "white"))
            shape = self.SHAPES.get(node.node_type, "box")
            lines.append(
                f'    {safe_id} [label="{label}" '
                f'shape={shape} fillcolor="{bg}" fontcolor="{fg}"]'
            )

        lines.append("")

        # -- Edges -----------------------------------------------------------
        lines.append("    // Edges")
        for edge in graph.edges:
            src = self._sanitize_id(edge.source)
            tgt = self._sanitize_id(edge.target)
            label = self._edge_label(edge)

            attrs = [f'label="{label}"']

            if edge.edge_type == EdgeType.USES_DOMAIN:
                attrs.append("style=dashed")
                attrs.append('color="#50C878"')
            elif edge.edge_type == EdgeType.RELATIONSHIP:
                attrs.append("dir=both")
                attrs.append('color="#6CB4EE"')
            elif edge.edge_type == EdgeType.TOPOLOGY_RULE:
                attrs.append('color="#E85D5D"')
            elif edge.edge_type == EdgeType.CONTROLLER:
                attrs.append("style=bold")
                attrs.append('color="#9B59B6"')

            lines.append(f"    {src} -> {tgt} [{', '.join(attrs)}]")

        lines.append("}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown Exporter
# ---------------------------------------------------------------------------

@register_exporter
class MarkdownExporter(BaseExporter):
    """
    Export as a Markdown summary document.

    Human-readable table format — great for documentation and issue trackers.
    """
    format_name = "markdown"
    file_extension = ".md"
    content_type = "text/markdown"

    def export(self, graph: Graph) -> str:
        lines = [
            f"# Schema: {graph.name}",
            "",
            f"**Path:** `{graph.path}`",
            "",
        ]

        # -- Stats -----------------------------------------------------------
        stats = graph.stats
        lines.append("## Summary")
        lines.append("")
        lines.append(f"| Metric | Count |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Nodes | {stats['total_nodes']} |")
        lines.append(f"| Total Edges | {stats['total_edges']} |")
        for ntype, count in stats.get("node_types", {}).items():
            lines.append(f"| {ntype.replace('_', ' ').title()} | {count} |")
        lines.append("")

        # -- Feature Classes -------------------------------------------------
        fcs = graph.get_nodes_by_type(NodeType.FEATURE_CLASS)
        if fcs:
            lines.append("## Feature Classes")
            lines.append("")
            lines.append("| Name | Geometry | Fields | Dataset |")
            lines.append("|------|----------|--------|---------|")
            for fc in fcs:
                geom = fc.properties.get("geometry_type", "?")
                field_count = fc.properties.get("field_count", "?")
                ds = fc.properties.get("feature_dataset", "—")
                lines.append(f"| {fc.name} | {geom} | {field_count} | {ds} |")
            lines.append("")

        # -- Tables ----------------------------------------------------------
        tables = graph.get_nodes_by_type(NodeType.TABLE)
        if tables:
            lines.append("## Tables")
            lines.append("")
            lines.append("| Name | Fields |")
            lines.append("|------|--------|")
            for tbl in tables:
                field_count = tbl.properties.get("field_count", "?")
                lines.append(f"| {tbl.name} | {field_count} |")
            lines.append("")

        # -- Domains ---------------------------------------------------------
        domains = graph.get_nodes_by_type(NodeType.DOMAIN)
        if domains:
            lines.append("## Domains")
            lines.append("")
            lines.append("| Name | Type | Values |")
            lines.append("|------|------|--------|")
            for dom in domains:
                dtype = dom.properties.get("domain_type", "?")
                coded = dom.properties.get("coded_values", {})
                if isinstance(coded, dict):
                    count = len(coded)
                elif isinstance(coded, list):
                    count = len(coded)
                else:
                    count = 0
                val_str = f"{count} values" if count else "—"
                lines.append(f"| {dom.name} | {dtype} | {val_str} |")
            lines.append("")

        # -- Relationship Classes --------------------------------------------
        rels = graph.get_nodes_by_type(NodeType.RELATIONSHIP_CLASS)
        if rels:
            lines.append("## Relationship Classes")
            lines.append("")
            lines.append("| Name | Origin | Destination | Cardinality |")
            lines.append("|------|--------|-------------|-------------|")
            for rel in rels:
                origin = ", ".join(rel.properties.get("origin_classes", []))
                dest = ", ".join(rel.properties.get("destination_classes", []))
                card = rel.properties.get("cardinality", "?")
                lines.append(f"| {rel.name} | {origin} | {dest} | {card} |")
            lines.append("")

        # -- Topologies ------------------------------------------------------
        topos = graph.get_nodes_by_type(NodeType.TOPOLOGY)
        if topos:
            lines.append("## Topologies")
            lines.append("")
            for topo in topos:
                lines.append(f"### {topo.name}")
                lines.append(f"- **Dataset:** {topo.properties.get('feature_dataset', '?')}")
                lines.append(f"- **Rules:** {topo.properties.get('rule_count', 0)}")
                rules = topo.properties.get("rules", [])
                if rules:
                    lines.append("")
                    lines.append("| Rule | Origin | Destination |")
                    lines.append("|------|--------|-------------|")
                    for rule in rules:
                        lines.append(
                            f"| {rule.get('rule_type', '?')} "
                            f"| {rule.get('origin', '?')} "
                            f"| {rule.get('destination', '—')} |"
                        )
                lines.append("")

        # -- Metadata --------------------------------------------------------
        if graph.metadata:
            lines.append("## Metadata")
            lines.append("")
            for key, val in graph.metadata.items():
                lines.append(f"- **{key}:** {val}")
            lines.append("")

        return "\n".join(lines)
