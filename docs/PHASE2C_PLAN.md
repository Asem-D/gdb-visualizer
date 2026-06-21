# Phase 2c: Esri Schema Report Integration

## Overview

Integrate ArcGIS Pro's `Generate Schema Report` geoprocessing tool output as a complementary feature in gdb-visualizer. For large geodatabases that produce unusable diagrams, gracefully degrade to the Esri HTML report with Excel download.

---

## 1. Architecture Decision

### What we're adding

| Component | Description |
|-----------|-------------|
| `schema_report.py` | New module: calls `arcpy.management.SchemaReport()` to generate HTML + optional Excel |
| Large schema detection | Node-count threshold to decide when diagrams are unusable |
| CLI `--schema-report` flag | Opt-in flag on `extract` to also generate the Esri HTML report |
| CLI `--report-only` flag | Skip visualization, just generate the report |
| `visualization.html` update | Detect large schemas → show "Report mode" with HTML embed + Excel download button |
| New `serve` integration | Serve the Esri report HTML alongside the D3 visualization |

### What we're NOT doing

- NOT replacing D3/Mermaid/JSON/Table views for small/medium schemas
- NOT bundling or distributing Esri's HTML template
- NOT requiring the Esri report for normal operation
- NOT making it a separate tool — it's an enhancement to the existing pipeline

---

## 2. Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `gdbviz/schema_report.py` | Wraps `arcpy.management.SchemaReport()`, handles HTML/Excel output |
| `tests/test_schema_report.py` | Tests for report generation logic (mocked arcpy) |

### Modified Files

| File | Changes |
|------|---------|
| `gdbviz/cli.py` | Add `--schema-report` and `--report-only` flags to `extract`; add `report` subcommand |
| `gdbviz/models.py` | Add `is_large_schema()` method to Graph |
| `gdbviz/extractor/arcpy_extractor.py` | No changes needed — extraction is separate from reporting |
| `static/visualization.html` | Add large-schema detection, "report mode" view, Excel download |
| `gdbviz/serve.py` | (or inline in cli.py) Serve Esri report HTML alongside D3 assets |
| `README.md` | Document new feature, large-schema behavior |
| `pyproject.toml` | No new deps (arcpy already required for report generation) |

---

## 3. Detailed Design

### 3.1 Schema Report Generator (`gdbviz/schema_report.py`)

```python
"""Generate Esri Schema Report HTML from a geodatabase (requires arcpy)."""

from pathlib import Path

class SchemaReportGenerator:
    """Wraps arcpy.management.SchemaReport()."""
    
    def is_available() -> bool:
        """Check if arcpy is importable."""
    
    def generate(
        gdb_path: Path,
        output_path: Path,
        output_format: str = "html",       # "html" or "excel"
        include_fields: bool = True,
        include_domains: bool = True,
        include_subtypes: bool = True,
        include_attribute_rules: bool = True,
        include_dataset_properties: bool = True,
    ) -> Path:
        """
        Run SchemaReport GP tool, return path to generated file.
        
        For HTML: generates a self-contained .html file
        For Excel: generates .xlsx (requires openpyxl)
        """
```

**Key implementation notes:**
- The GP tool is `arcpy.management.SchemaReport(gdb_path, output_path)`
- Parameters: https://pro.arcgis.com/en/pro-app/latest/tool-reference/data-management/generate-schema-report.htm
- HTML output is self-contained (CSS/JS inline) — easy to serve
- Excel output requires `openpyxl` (ArcGIS Pro's Python has it)
- We should catch arcpy errors gracefully and report them

### 3.2 Large Schema Detection (`gdbviz/models.py`)

Add to `Graph`:

```python
# Thresholds (tunable)
LARGE_SCHEMA_THRESHOLD = 150     # nodes — diagrams become cluttered
HUGE_SCHEMA_THRESHOLD = 400      # nodes — diagrams become unusable

@property
def schema_size(self) -> str:
    """Classify schema size for UI decisions."""
    n = self.stats["total_nodes"]
    if n >= HUGE_SCHEMA_THRESHOLD:
        return "huge"
    elif n >= LARGE_SCHEMA_THRESHOLD:
        return "large"
    return "normal"

@property
def is_visualization_recommended(self) -> bool:
    """Whether interactive visualization is recommended."""
    return self.schema_size == "normal"
```

### 3.3 CLI Changes (`gdbviz/cli.py`)

#### Modified `extract` command

```bash
# Existing behavior (unchanged)
gdbviz extract --path ./MyProject.gdb --format json

# NEW: Also generate Esri HTML report alongside
gdbviz extract --path ./MyProject.gdb --format json --schema-report

# NEW: Report only (no visualization JSON)
gdbviz extract --path ./MyProject.gdb --report-only

# NEW: Generate Excel report
gdbviz extract --path ./MyProject.gdb --schema-report --report-format excel
```

New CLI options:
- `--schema-report` / `-r` (flag): Generate Esri HTML report alongside normal output
- `--report-only` (flag): Only generate the report, skip normal extraction/export
- `--report-format` : `html` (default) or `excel`
- `--report-output` : Custom output path for the report file

#### Modified `visualize` command

```bash
# If schema_report.html exists alongside schema.json, serve it too
gdbviz visualize --schema schema.json
# → visualization.html auto-detects large schema + shows report mode
```

### 3.4 Visualization.html Changes

#### Large Schema Detection (JS)

```javascript
// On schema load, check node count
const nodeCount = schemaData.nodes.length;
const HUGE_THRESHOLD = 400;
const LARGE_THRESHOLD = 150;

if (nodeCount >= HUGE_THRESHOLD) {
    showReportMode();   // Hide D3/Mermaid, show Esri report embed
} else if (nodeCount >= LARGE_THRESHOLD) {
    showLargeSchemaWarning();  // Show warning but still render
}
```

#### Report Mode UI

When triggered (huge schema + esri_report.html exists):

```
┌──────────────────────────────────────────────────┐
│  ⚠️  Large Schema (XXX nodes)                    │
│  Interactive diagrams are not recommended for    │
│  schemas this size.                              │
│                                                  │
│  Showing Esri Schema Report instead.             │
│                                                  │
│  [📥 Download HTML]  [📥 Download Excel]          │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │                                            │  │
│  │     Esri Schema Report (embedded iframe)   │  │
│  │                                            │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ── Or view raw data ──                          │
│  [D3 Graph] [Mermaid] [Table] [JSON]            │
│  (shown with warning that performance may be poor)│
└──────────────────────────────────────────────────┘
```

When large schema but NO esri report exists:

```
┌──────────────────────────────────────────────────┐
│  ⚠️  Large Schema (XXX nodes)                    │
│  This schema may cause slow rendering.           │
│  Consider generating an Esri Schema Report:      │
│  gdbviz extract --path ... --schema-report       │
│                                                  │
│  [D3 Graph] [Mermaid] [Table] [JSON]            │
│  (still functional, just slower)                 │
└──────────────────────────────────────────────────┘
```

### 3.5 Serve Integration

When `gdbviz visualize` starts:
1. Check if `esri_report.html` exists in the same directory as `schema.json`
2. If yes, serve it at `/esri_report.html`
3. Pass its availability to visualization.html via the schema JSON metadata
4. Also check for `schema_report.xlsx` for download link

```python
# In the serve logic:
def _find_report_assets(schema_dir: Path) -> dict:
    """Find Esri report files alongside schema."""
    assets = {}
    html_report = schema_dir / "esri_report.html"
    if html_report.exists():
        assets["esri_report_html"] = str(html_report)
    excel_report = schema_dir / "esri_report.xlsx"
    if excel_report.exists():
        assets["esri_report_excel"] = str(excel_report)
    return assets
```

---

## 4. Implementation Order

| Step | Task | Depends On |
|------|------|------------|
| 1 | Create `gdbviz/schema_report.py` | — |
| 2 | Add `schema_size` property to `models.py` | — |
| 3 | Add `--schema-report` / `--report-only` to CLI `extract` | Step 1 |
| 4 | Create `tests/test_schema_report.py` | Step 1 |
| 5 | Update `visualization.html` — large schema warning | Step 2 |
| 6 | Update `visualization.html` — report mode with iframe embed | Step 5 |
| 7 | Update serve logic to find and serve report assets | Step 1 |
| 8 | Update README.md with new features | Steps 1–7 |
| 9 | Run all tests (existing + new) | All steps |

---

## 5. Test Plan

| Test | Type | Notes |
|------|------|-------|
| `SchemaReportGenerator.is_available()` | Unit | Mock arcpy import |
| `SchemaReportGenerator.generate()` — HTML | Unit | Mock `arcpy.management.SchemaReport` |
| `SchemaReportGenerator.generate()` — Excel | Unit | Mock arcpy |
| `SchemaReportGenerator.generate()` — arcpy missing | Unit | Should raise clear error |
| `Graph.schema_size` — normal/large/huge | Unit | Pure logic |
| `Graph.is_visualization_recommended` | Unit | Pure logic |
| CLI `--schema-report` flag | Integration | Mock arcpy, check file output |
| CLI `--report-only` flag | Integration | Mock arcpy, check no JSON output |
| Large schema detection in viz HTML | Manual | Create test schema with 500+ nodes |
| Report mode UI in viz HTML | Manual | Verify iframe embed + download buttons |
| Existing tests still pass | Regression | `pytest` must remain green |

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| ArcGIS Pro not installed → can't generate report | `is_available()` check; clear error message suggesting ArcGIS Pro |
| Large HTML report won't fit in iframe | Use full-width iframe with scroll, not fixed dimensions |
| Excel export requires openpyxl | Check dependency; ArcGIS Pro Python includes it; note in docs |
| Users confused by sudden UI change on large schemas | Clear messaging: "This schema is large — showing detailed report instead" |
| Report generation is slow on huge GDBs | Run in background; show progress indicator |
| Esri's HTML report format changes between ArcGIS Pro versions | We just serve whatever the GP tool outputs — no parsing of their HTML |

---

## 7. README Updates

Add to Features section:
```
- 📋 **Esri Schema Report** — optional integration with ArcGIS Pro's built-in schema report
  for large geodatabases where interactive diagrams are impractical
- 📐 **Large schema detection** — automatic graceful degradation when schemas exceed visual limits
```

Add to CLI Reference:
```
### Schema Report Options (extract command)

| Option | Description |
|--------|-------------|
| `--schema-report` | Generate Esri HTML schema report alongside output |
| `--report-only` | Only generate report, skip normal extraction |
| `--report-format` | Report format: `html` (default) or `excel` |
| `--report-output` | Custom output path for report file |
```

Add to Roadmap:
```
- [x] **Phase 2c** — Esri Schema Report integration (large schema handling)
```

---

## 8. Non-Goals (Out of Scope)

- Parsing or modifying the Esri HTML report content
- Custom HTML report generation (we use Esri's tool as-is)
- Making the report generation async/background (keep it simple first)
- Supporting non-Esri report formats
- Automatic report generation on every extract (must be opt-in with flag)
