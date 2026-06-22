# gdb-visualizer

> **Interactive geodatabase schema visualization** — extract, explore, and share your ArcGIS geodatabase structure as interactive graphs, Mermaid diagrams, PlantUML, or Graphviz DOT.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/Asem-D/gdb-visualizer)

---

## Why?

Every GIS team has this problem: someone joins, gets access to 15 geodatabases, and asks *"what's actually in these?"*

The existing tools fall short:
- **Generate Schema Report** → flat CSV, no relationships
- **ArcGIS Diagrammer** → deprecated, crashes on complex schemas
- **Schema Viewer** → static text only

**gdb-visualizer** gives you an interactive graph: feature classes, tables, fields, domains, relationship classes, topology rules, subtypes — all connected. See the forest *and* the trees.

---

## Features

- 🔷 **Full extraction** — feature classes, tables, fields, domains, relationship classes, topology, subtypes
- 📊 **Multiple output formats** — JSON, Mermaid, PlantUML, Graphviz DOT, Markdown
- 🖥️ **CLI-first** — works in any terminal, CI/CD pipeline, or automation script
- 🔌 **No ArcGIS required** (basic mode) — GDAL/OGR fallback for feature classes + fields
- 📦 **Zero config** — `pip install` and go
- 🧪 **Tested** — unit tests for models and exporters
- 🌐 **Interactive visualization** — D3.js force-directed graph with dark theme, filtering, drill-down details
- 📋 **Esri Schema Report** — Generate HTML/Excel schema reports via ArcGIS Pro, served in-app for large schemas
- ⚡ **Large schema detection** — Automatic warnings for schemas >150 nodes, integrated report viewer for >400 nodes

---

## Installation

```bash
# Clone
git clone https://github.com/sem-daaboul/gdb-visualizer.git
cd gdb-visualizer

# Install
pip install -e .

# With dev tools
pip install -e ".[dev]"
```

### Requirements

| Feature | Requirement |
|---------|-------------|
| CLI + Exporters | Python 3.10+ (no ArcGIS needed) |
| Full extraction (domains, relationships, topology) | ArcGIS Pro |
| Basic extraction (feature classes + fields only) | GDAL/OGR with OpenFileGDB driver |

---

## Quick Start

### Extract a schema (JSON)

```bash
gdbviz extract --path ./MyProject.gdb --format json
```

### Export as Mermaid diagram

```bash
gdbviz extract --path ./MyProject.gdb --format mermaid --output schema.mmd
```

Paste into [mermaid.live](https://mermaid.live/) for instant visualization.

### Export as PlantUML

```bash
gdbviz extract --path ./MyProject.gdb --format plantuml --output schema.puml
```

Render at [plantuml.com](https://www.plantuml.com/plantuml/) or in VS Code with the PlantUML extension.

### Export as Graphviz DOT

```bash
gdbviz extract --path ./MyProject.gdb --format dot --output schema.dot
dot -Tpng schema.dot -o schema.png
```

### Run the demo (no .gdb needed)

```bash
gdbviz demo --format json
gdbviz demo --format mermaid
```

---

## CLI Reference

### `gdbviz extract`

| Option | Short | Description |
|--------|-------|-------------|
| `--path` | `-p` | Path to the .gdb **(required)** |
| `--format` | `-f` | Output format: `json`, `mermaid`, `plantuml`, `dot`, `markdown` |
| `--output` | `-o` | Output file path |
| `--extractor` | `-e` | Backend: `auto`, `arcpy`, `ogr` |
| `--schema-report` | `-r` | Also generate Esri HTML Schema Report alongside output |
| `--report-only` | | Only generate report, skip normal extraction/export |
| `--report-format` | | Schema report format: `html` (default) or `excel` |
| `--report-output` | | Custom output path for the schema report |
| `--no-color` | | Disable colored output |

```bash
# Generate a schema report alongside extraction
gdbviz extract --path ./MyProject.gdb --format json --schema-report

# Generate only the Esri HTML report
gdbviz extract --path ./MyProject.gdb --report-only

# Generate Excel report to custom location
gdbviz extract -p ./MyProject.gdb --report-only --report-format excel --report-output report.xlsx
```

### `gdbviz visualize`

Serve the D3.js interactive visualization in a browser.

| Option | Short | Description |
|--------|-------|-------------|
| `--schema` | `-s` | Path to schema JSON file **(required)** |
| `--port` | | HTTP server port (default: 8080) |
| `--no-open` | | Don't auto-open browser |

```bash
# Extract then visualize
gdbviz extract --path ./MyProject.gdb --format json -o schema.json
gdbviz visualize --schema schema.json

# Quick demo
gdbviz demo --format json -o schema.json
gdbviz visualize --schema schema.json
```

### `gdbviz demo`

Run with a sample schema to see what gdbviz can do.

### `gdbviz formats`

List available export formats.

### `gdbviz extractors`

List available extraction backends and their status.

---

## Output Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| **JSON** | `.json` | D3.js visualization, API consumption, programmatic access |
| **Mermaid** | `.mmd` | GitHub READMEs, documentation, quick diagrams |
| **PlantUML** | `.puml` | Detailed class/relationship diagrams, enterprise docs |
| **Graphviz DOT** | `.dot` | High-quality renderings, publication diagrams |
| **Markdown** | `.md` | Issue trackers, documentation, human-readable summaries |

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  Geodatabase │────▶   Extractor   │────▶     Graph   │
│   (.gdb)     │     │  (arcpy/ogr) │     │   (Model)   │
└──────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌──────────────┐     ┌───────▼───────┐
                    │  JSON file   │◀────│  Exporter     │
                    │  .mmd file   │◀────│  (json/mmd/   │
                    │  .puml file  │◀────│   puml/dot/   │
                    │  .dot file   │◀────│   md)         │
                    │  .md file    │◀────│               │
                    └──────────────┘     └───────────────┘
```

**Key design decisions:**
- **Graph model as intermediate representation** — extractors produce a Graph, exporters consume it. New backends on either side don't affect the other.
- **CLI-first** — no GUI dependency. Works in headless environments, CI/CD, remote servers.
- **Dual extraction** — ArcGIS for full extraction, GDAL for basic extraction. The tool works even without ArcGIS installed.

---

## Schema Graph Model

### Node Types

| Type | Description |
|------|-------------|
| `feature_dataset` | Spatial container for feature classes |
| `feature_class` | Spatial or non-spatial class with geometry |
| `table` | Standalone attribute table |
| `domain` | Coded value or range domain |
| `topology` | Spatial topology with rules |
| `network` | Network dataset |
| `relationship_class` | Defines relationships between classes |
| `attribute_rule` | Calculation/constraint/validation rule |

### Edge Types

| Type | Description |
|------|-------------|
| `contains` | FeatureDataset → FeatureClass/Table |
| `relationship` | FC/Table ↔ FC/Table via RelationshipClass |
| `uses_domain` | Field → Domain |
| `topology_rule` | Topology → FeatureClass |
| `has_subtypes` | FeatureClass → Subtype codes |
| `controller` | FeatureDataset → Topology/Network |

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repo
2. Create a feature branch
3. Add tests for new functionality
4. Run `pytest` to verify
5. Submit a pull request

---

## Roadmap

- [x] **Phase 1** — CLI extraction + multi-format export
- [x] **Phase 2a** — D3.js interactive visualization (standalone HTML with HTTP server)
- [x] **Phase 2b** — Format tabs (D3/Mermaid/Table/JSON) with dark theme
- [x] **Phase 2c** — Esri Schema Report integration + large schema detection + Report Mode
- [ ] **Phase 2d** — Jupyter widget integration
- [ ] **Phase 3** — Advanced features (diff, bookmarks, annotations)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built for the GIS community that deserved better tooling
- Inspired by [SchemaSpy](https://schemaspy.org/) (database schema visualization)
- D3.js force-directed graph pattern from [Obsidian Graph View](https://obsidian.md/)
