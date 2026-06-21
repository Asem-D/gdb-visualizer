"""
CLI entry point for gdbviz.

Commands:
    gdbviz extract    — Extract schema from a geodatabase
    gdbviz visualize  — Serve D3.js visualization (Phase 2)
    gdbviz demo       — Run demo with sample schema
    gdbviz formats    — List available export formats
    gdbviz extractors — List available extraction backends
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import click
    from click import Context
except ImportError:
    print("Error: 'click' is required. Install with: pip install click")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from gdbviz import __version__
from gdbviz.models import Graph
from gdbviz.extractor import list_extractors, auto_select_extractor, get_extractor
from gdbviz.exporter import list_formats, get_exporter


console = Console() if HAS_RICH else None


def _print(msg: str = "", **kwargs) -> None:
    """Print with rich if available, otherwise plain."""
    if console:
        console.print(msg, **kwargs)
    else:
        print(msg)


def _find_report_assets(schema_dir: Path) -> dict[str, Path]:
    """Find Esri Schema Report files alongside the schema JSON.

    Looks for common naming patterns:
      - esri_schema_report.html / esri_schema_report.xlsx
      - schema_report.html / schema_report.xlsx

    Returns dict mapping asset key ('html', 'excel') → file Path.
    """
    assets = {}
    candidates_html = [
        "esri_schema_report.html",
        "schema_report.html",
        "SchemaReport.html",
    ]
    candidates_xlsx = [
        "esri_schema_report.xlsx",
        "schema_report.xlsx",
        "SchemaReport.xlsx",
    ]
    for name in candidates_html:
        p = schema_dir / name
        if p.exists():
            assets["html"] = p
            break
    for name in candidates_xlsx:
        p = schema_dir / name
        if p.exists():
            assets["excel"] = p
            break
    return assets


@click.group()
@click.version_option(version=__version__, prog_name="gdbviz")
@click.pass_context
def cli(ctx: Context) -> None:
    """
    gdbviz — Interactive geodatabase schema visualization.

    Extract, explore, and share your ArcGIS geodatabase structure
    as interactive graphs, Mermaid diagrams, PlantUML, or Graphviz DOT.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    "--path", "-p",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to the geodatabase (.gdb)",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: schema.<ext> in current directory)",
)
@click.option(
    "--format", "-f",
    "fmt",
    type=click.Choice(list_formats(), case_sensitive=False),
    default="json",
    help="Output format (default: json)",
)
@click.option(
    "--extractor", "-e",
    type=click.Choice(["auto", "arcpy", "ogr"], case_sensitive=False),
    default="auto",
    help="Extraction backend (default: auto — prefers arcpy)",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output",
)
@click.option(
    "--schema-report", "-r",
    is_flag=True,
    help="Also generate Esri HTML Schema Report alongside output",
)
@click.option(
    "--report-only",
    is_flag=True,
    help="Only generate report, skip normal extraction/export",
)
@click.option(
    "--report-format",
    type=click.Choice(["html", "excel"], case_sensitive=False),
    default="html",
    help="Schema report format (default: html)",
)
@click.option(
    "--report-output",
    type=click.Path(path_type=Path),
    default=None,
    help="Custom output path for the schema report",
)
@click.pass_context
def extract(
    ctx: Context,
    path: Path,
    output: Path | None,
    fmt: str,
    extractor: str,
    no_color: bool,
    schema_report: bool,
    report_only: bool,
    report_format: str,
    report_output: Path | None,
) -> None:
    """
    Extract schema from a geodatabase and export to a file.

    Examples:

        gdbviz extract --path ./MyProject.gdb --format json

        gdbviz extract -p ./MyProject.gdb -f mermaid -o schema.mmd

        gdbviz extract -p ./MyProject.gdb -f plantuml -o schema.puml

        gdbviz extract -p ./MyProject.gdb -f dot -o schema.dot

        gdbviz extract -p ./MyProject.gdb -r --schema-report

        gdbviz extract -p ./MyProject.gdb --report-only --report-format excel
    """
    _print(f"\n[bold cyan]gdb-visualizer[/] v{__version__}\n")

    # -- Validate path ------------------------------------------------------
    gdb_path = Path(path)
    if not gdb_path.exists():
        _print(f"[red]Error:[/] Path does not exist: {gdb_path}")
        sys.exit(1)
    if not gdb_path.suffix == ".gdb":
        _print(f"[yellow]Warning:[/] Path does not end in .gdb — attempting anyway")

    # -- Select extractor ---------------------------------------------------
    _print("[bold]Selecting extraction backend...[/]")

    if extractor == "auto":
        try:
            ext = auto_select_extractor()
        except RuntimeError as e:
            _print(f"[red]Error:[/] {e}")
            sys.exit(1)
    else:
        ext = get_extractor(extractor)
        if not ext.is_available():
            _print(f"[red]Error:[/] Extractor '{extractor}' is not available.")
            _print("Available extractors:")
            for info in list_extractors():
                status = "[green]OK[/]" if info["available"] else "[red]NO[/]"
                _print(f"  {status} {info['name']} — {info['description']}")
            sys.exit(1)

    _print(f"  Using: [green]{ext.name}[/] — {ext.description}\n")

    # -- Extract ------------------------------------------------------------
    _print(f"[bold]Extracting schema from:[/] {gdb_path}")
    try:
        graph = ext.extract(gdb_path)
    except Exception as e:
        _print(f"\n[red]Extraction failed:[/] {e}")
        sys.exit(1)

    # -- Stats --------------------------------------------------------------
    stats = graph.stats
    _print(f"\n[bold green]Extraction complete![/]")
    _print(f"  Nodes: {stats['total_nodes']}  |  Edges: {stats['total_edges']}")
    for ntype, count in stats.get("node_types", {}).items():
        _print(f"    {ntype}: {count}")
    _print()

    # -- Schema size warning ------------------------------------------------
    schema_size = graph.schema_size
    if schema_size == "huge":
        _print(
            f"[bold red]⚠  Large schema detected ({stats['total_nodes']} nodes).[/]\n"
            f"  Interactive diagrams may be unusable at this scale.\n"
            f"  Consider: gdbviz extract -p {gdb_path} --report-only\n"
        )
    elif schema_size == "large":
        _print(
            f"[yellow]⚠  Moderate schema ({stats['total_nodes']} nodes).[/]\n"
            f"  Diagrams may be cluttered. For better readability, consider:\n"
            f"  gdbviz extract -p {gdb_path} --schema-report\n"
        )

    # -- Schema Report (Esri HTML) ------------------------------------------
    if schema_report or report_only:
        from gdbviz.schema_report import SchemaReportGenerator, SchemaReportError

        if not SchemaReportGenerator.is_available():
            _print(
                "[red]Error:[/] Schema report requires arcpy (ArcGIS Pro).\n"
                "Install ArcGIS Pro or run in its Python environment."
            )
            if not report_only:
                _print("[yellow]Continuing with normal extraction...[/]\n")
            else:
                sys.exit(1)

        # Determine report output path
        if report_output:
            rpt_path = report_output
        else:
            ext = ".xlsx" if report_format == "excel" else ".html"
            # Place report alongside the schema output or in CWD
            if output:
                rpt_path = output.parent / f"esri_schema_report{ext}"
            else:
                rpt_path = Path(f"esri_schema_report{ext}")

        _print(f"[bold]Generating Esri Schema Report ({report_format})...[/]")
        try:
            result_path = SchemaReportGenerator.generate(
                gdb_path=gdb_path,
                output_path=rpt_path,
                output_format=report_format,
            )
            _print(f"  [green]OK[/] Report written to: {result_path}\n")
        except SchemaReportError as e:
            _print(f"  [red]Report generation failed:[/] {e}\n")
            if report_only:
                sys.exit(1)

        if report_only:
            _print("[bold cyan]Done![/] Report-only mode. Exiting.\n")
            return

    # -- Export -------------------------------------------------------------
    exporter = get_exporter(fmt)

    if output is None:
        output = Path(f"schema{exporter.file_extension}")

    _print(f"[bold]Exporting to {fmt.upper()}:[/] {output}")
    exporter.export_to_file(graph, output)
    _print(f"  [green]OK[/] Written to {output}\n")

    # -- Done ---------------------------------------------------------------
    _print("[bold cyan]Done![/] Use the output file as needed:")
    if fmt == "json":
        _print(f"  gdbviz visualize --schema {output}")
    elif fmt == "mermaid":
        _print(f"  Paste into https://mermaid.live/")
    elif fmt == "plantuml":
        _print(f"  Render at https://www.plantuml.com/plantuml/")
    elif fmt == "dot":
        _print(f"  Render with: dot -Tpng {output} -o schema.png")
    elif fmt == "markdown":
        _print(f"  Open in any Markdown viewer")
    _print()


@cli.command()
@click.option(
    "--schema", "-s",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to schema JSON file",
)
@click.option(
    "--port",
    type=int,
    default=8080,
    help="Port for the visualization server (default: 8080)",
)
@click.option(
    "--no-open",
    is_flag=True,
    help="Don't auto-open browser",
)
@click.pass_context
def visualize(ctx: Context, schema: Path, port: int, no_open: bool) -> None:
    """
    Serve the D3.js interactive visualization in a browser.

    Requires a schema JSON file (from 'gdbviz extract -f json').
    Copies static assets + schema to a temp dir and serves via HTTP.
    """
    import http.server
    import shutil
    import tempfile
    import threading
    import webbrowser

    static_dir = Path(__file__).parent.parent / "static"

    if not (static_dir / "visualization.html").exists():
        _print("[red]Error:[/] visualization.html not found in static/")
        sys.exit(1)
    if not (static_dir / "js" / "d3.v7.min.js").exists():
        _print("[red]Error:[/] js/d3.v7.min.js not found in static/js/")
        sys.exit(1)

    _print(f"\n[bold cyan]gdb-visualizer[/] v{__version__} — Visualization Server\n")
    _print(f"  Schema:  {schema}")
    _print(f"  Port:    {port}\n")

    # Create a temp directory and copy assets + schema
    tmp = Path(tempfile.mkdtemp(prefix="gdbviz_"))
    try:
        shutil.copy2(static_dir / "visualization.html", tmp / "visualization.html")
        shutil.copytree(static_dir / "js", tmp / "js")
        shutil.copy2(schema, tmp / "schema.json")

        # -- Detect Esri Schema Report assets alongside schema JSON ---------
        schema_dir = schema.parent
        report_assets = _find_report_assets(schema_dir)
        if report_assets:
            for asset_key, asset_path in report_assets.items():
                dest = tmp / Path(asset_path).name
                shutil.copy2(asset_path, dest)
                report_assets[asset_key] = Path(asset_path).name
            _print(f"  [green]Schema report found:[/] {list(report_assets.values())}\n")

        _print(f"[bold]Starting server on http://localhost:{port}[/]\n")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(tmp), **kwargs)

            def log_message(self, format, *args):
                pass  # suppress noisy request logs

            def end_headers(self):
                self.send_header("Cache-Control", "no-cache")
                super().end_headers()

        server = http.server.HTTPServer(("127.0.0.1", port), Handler)
        url = f"http://localhost:{port}/visualization.html"

        if not no_open:
            threading.Timer(0.5, webbrowser.open, args=(url,)).start()

        _print(f"  [green]Serving:[/] {url}")
        _print(f"  [dim]Press Ctrl+C to stop[/]\n")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            _print("\n[yellow]Server stopped.[/]")
        finally:
            server.server_close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@cli.command()
@click.option(
    "--format", "-f",
    "fmt",
    type=click.Choice(list_formats(), case_sensitive=False),
    default="json",
    help="Output format for the demo",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: demo_schema.<ext>)",
)
def demo(fmt: str, output: Path | None) -> None:
    """
    Run a demo with a sample geodatabase schema.

    Shows what gdbviz can do without needing an actual .gdb file.
    """
    _print(f"\n[bold cyan]gdb-visualizer[/] v{__version__} — Demo Mode\n")

    # Load sample schema
    sample_path = Path(__file__).parent.parent / "examples" / "sample_schema.json"
    if not sample_path.exists():
        # Fallback: create a sample graph inline
        _print("[yellow]Sample schema not found, generating inline demo...[/]\n")
        graph = _create_demo_graph()
    else:
        _print(f"[bold]Loading sample schema:[/] {sample_path}\n")
        graph = Graph.from_json(sample_path.read_text(encoding="utf-8"))

    # Export
    exporter = get_exporter(fmt)
    if output is None:
        output = Path(f"demo_schema{exporter.file_extension}")

    exporter.export_to_file(graph, output)
    _print(f"[green]OK[/] Demo exported to {output} ({fmt.upper()})\n")

    stats = graph.stats
    _print(f"  Nodes: {stats['total_nodes']}  |  Edges: {stats['total_edges']}")
    for ntype, count in stats.get("node_types", {}).items():
        _print(f"    {ntype}: {count}")
    _print()


@cli.command(name="formats")
def list_formats_cmd() -> None:
    """List all available export formats."""
    if console:
        table = Table(title="Export Formats")
        table.add_column("Format", style="cyan")
        table.add_column("Extension", style="green")
        table.add_column("Description")

        descriptions = {
            "json": "Primary interchange format (D3.js compatible)",
            "mermaid": "Mermaid.js flowchart (GitHub, docs)",
            "plantuml": "PlantUML class diagram",
            "dot": "Graphviz DOT language",
            "markdown": "Markdown table summary",
        }

        for fmt in list_formats():
            exp = get_exporter(fmt)
            table.add_row(
                fmt,
                exp.file_extension,
                descriptions.get(fmt, ""),
            )
        console.print(table)
    else:
        print("Available formats:")
        for fmt in list_formats():
            exp = get_exporter(fmt)
            print(f"  {fmt:12s}  ({exp.file_extension})")


@cli.command(name="extractors")
def list_extractors_cmd() -> None:
    """List available extraction backends."""
    if console:
        table = Table(title="Extraction Backends")
        table.add_column("Backend", style="cyan")
        table.add_column("Status")
        table.add_column("Description")

        for info in list_extractors():
            status = "[green]Available[/]" if info["available"] else "[red]Not installed[/]"
            table.add_row(info["name"], status, info["description"])
        console.print(table)
    else:
        print("Extraction backends:")
        for info in list_extractors():
            status = "OK" if info["available"] else "NO"
            print(f"  {status} {info['name']:8s} — {info['description']}")


def _create_demo_graph() -> Graph:
    """Create a sample graph for demo mode (no file needed)."""
    from gdbviz.models import Node, Edge, NodeType, EdgeType

    gdb_name = "CityGIS_Sample"
    gdb_path = "C:\\Data\\CityGIS.gdb"

    graph = Graph(
        name=gdb_name,
        path=gdb_path,
        metadata={
            "extractor": "demo",
            "note": "This is a sample schema for demonstration purposes.",
        },
    )

    # Feature datasets
    fd_infra = "feature_dataset://Infrastructure"
    fd_land = "feature_dataset://LandUse"
    fd_util = "feature_dataset://Utilities"

    graph.add_node(Node(id=fd_infra, name="Infrastructure", node_type=NodeType.FEATURE_DATASET,
                        properties={"spatial_reference": "WGS_1984_UTM_Zone_37N"}))
    graph.add_node(Node(id=fd_land, name="LandUse", node_type=NodeType.FEATURE_DATASET,
                        properties={"spatial_reference": "WGS_1984_UTM_Zone_37N"}))
    graph.add_node(Node(id=fd_util, name="Utilities", node_type=NodeType.FEATURE_DATASET,
                        properties={"spatial_reference": "WGS_1984_UTM_Zone_37N"}))

    # Feature classes
    fc_road = "feature_class://CityGIS.gdb\\Infrastructure\\Roads"
    fc_bridge = "feature_class://CityGIS.gdb\\Infrastructure\\Bridges"
    fc_parcel = "feature_class://CityGIS.gdb\\LandUse\\Parcels"
    fc_zoning = "feature_class://CityGIS.gdb\\LandUse\\Zoning"
    fc_pipe = "feature_class://CityGIS.gdb\\Utilities\\WaterPipes"
    fc_pump = "feature_class://CityGIS.gdb\\Utilities\\PumpStations"

    graph.add_node(Node(id=fc_road, name="Roads", node_type=NodeType.FEATURE_CLASS,
                        properties={"geometry_type": "Polyline", "field_count": 8,
                                    "feature_dataset": "Infrastructure",
                                    "fields": [
                                        {"name": "OBJECTID", "field_type": "OID", "is_oid": True},
                                        {"name": "Shape", "field_type": "Geometry", "is_shape": True},
                                        {"name": "RoadName", "field_type": "String", "length": 100},
                                        {"name": "RoadClass", "field_type": "SmallInteger", "domain": "RoadClassDomain"},
                                        {"name": "Width", "field_type": "Double"},
                                        {"name": "Surface", "field_type": "String", "domain": "SurfaceTypeDomain"},
                                    ]}))
    graph.add_node(Node(id=fc_bridge, name="Bridges", node_type=NodeType.FEATURE_CLASS,
                        properties={"geometry_type": "Point", "field_count": 6,
                                    "feature_dataset": "Infrastructure"}))
    graph.add_node(Node(id=fc_parcel, name="Parcels", node_type=NodeType.FEATURE_CLASS,
                        properties={"geometry_type": "Polygon", "field_count": 12,
                                    "feature_dataset": "LandUse",
                                    "fields": [
                                        {"name": "OBJECTID", "field_type": "OID", "is_oid": True},
                                        {"name": "ParcelID", "field_type": "String", "length": 20},
                                        {"name": "OwnerName", "field_type": "String", "length": 100},
                                        {"name": "LandUse", "field_type": "SmallInteger", "domain": "LandUseDomain"},
                                        {"name": "Area", "field_type": "Double"},
                                    ]}))
    graph.add_node(Node(id=fc_zoning, name="Zoning", node_type=NodeType.FEATURE_CLASS,
                        properties={"geometry_type": "Polygon", "field_count": 5,
                                    "feature_dataset": "LandUse"}))
    graph.add_node(Node(id=fc_pipe, name="WaterPipes", node_type=NodeType.FEATURE_CLASS,
                        properties={"geometry_type": "Polyline", "field_count": 10,
                                    "feature_dataset": "Utilities"}))
    graph.add_node(Node(id=fc_pump, name="PumpStations", node_type=NodeType.FEATURE_CLASS,
                        properties={"geometry_type": "Point", "field_count": 7,
                                    "feature_dataset": "Utilities"}))

    # Tables
    tbl_maint = "table://CityGIS.gdb\\MaintenanceLog"
    graph.add_node(Node(id=tbl_maint, name="MaintenanceLog", node_type=NodeType.TABLE,
                        properties={"field_count": 6}))

    # Domains
    dom_road = "domain://RoadClassDomain"
    dom_surface = "domain://SurfaceTypeDomain"
    dom_landuse = "domain://LandUseDomain"

    graph.add_node(Node(id=dom_road, name="RoadClassDomain", node_type=NodeType.DOMAIN,
                        properties={"domain_type": "codedValue",
                                    "coded_values": {1: "Highway", 2: "Arterial", 3: "Collector", 4: "Local"}}))
    graph.add_node(Node(id=dom_surface, name="SurfaceTypeDomain", node_type=NodeType.DOMAIN,
                        properties={"domain_type": "codedValue",
                                    "coded_values": {1: "Asphalt", 2: "Concrete", 3: "Gravel", 4: "Dirt"}}))
    graph.add_node(Node(id=fc_parcel + "#subtypes", name="ParcelSubtypes", node_type=NodeType.DOMAIN,
                        properties={"domain_type": "codedValue",
                                    "coded_values": {0: "Residential", 1: "Commercial", 2: "Industrial", 3: "Agricultural"}}))

    # Topology
    topo = "topology://CityGIS.gdb\\LandUse\\LandUse_Topology"
    graph.add_node(Node(id=topo, name="LandUse_Topology", node_type=NodeType.TOPOLOGY,
                        properties={"feature_dataset": "LandUse", "rule_count": 2,
                                    "rules": [
                                        {"rule_type": "Must Not Overlap", "origin": "Parcels"},
                                        {"rule_type": "Must Not Have Gaps", "origin": "Zoning"},
                                    ]}))

    # Controller dataset
    graph.add_edge(Edge(source=fd_land, target=topo, edge_type=EdgeType.CONTROLLER, label="controls"))

    # Containment edges
    for fc, fd in [(fc_road, fd_infra), (fc_bridge, fd_infra),
                    (fc_parcel, fd_land), (fc_zoning, fd_land),
                    (fc_pipe, fd_util), (fc_pump, fd_util)]:
        graph.add_edge(Edge(source=fd, target=fc, edge_type=EdgeType.CONTAINS, label="contains"))

    graph.add_edge(Edge(source=fd_land, target=tbl_maint, edge_type=EdgeType.CONTAINS, label="contains"))

    # Domain usage edges
    graph.add_edge(Edge(source=fc_road, target=dom_road, edge_type=EdgeType.USES_DOMAIN,
                        label="RoadClass → RoadClassDomain"))
    graph.add_edge(Edge(source=fc_road, target=dom_surface, edge_type=EdgeType.USES_DOMAIN,
                        label="Surface → SurfaceTypeDomain"))

    # Relationship class
    rel = "relclass://CityGIS.gdb\\Infrastructure\\Roads_PumpStations_Rel"
    graph.add_node(Node(id=rel, name="Roads_PumpStations_Rel", node_type=NodeType.RELATIONSHIP_CLASS,
                        properties={"origin_classes": ["Roads"], "destination_classes": ["PumpStations"],
                                    "cardinality": "OneToMany", "forward_label": "serves",
                                    "backward_label": "served by"}))
    graph.add_edge(Edge(source=fc_road, target=fc_pump, edge_type=EdgeType.RELATIONSHIP,
                        label="serves", properties={"relationship_class": "Roads_PumpStations_Rel"}))

    # Topology rules
    graph.add_edge(Edge(source=topo, target=fc_parcel, edge_type=EdgeType.TOPOLOGY_RULE,
                        label="Must Not Overlap"))
    graph.add_edge(Edge(source=topo, target=fc_zoning, edge_type=EdgeType.TOPOLOGY_RULE,
                        label="Must Not Have Gaps"))

    return graph


def main() -> None:
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
