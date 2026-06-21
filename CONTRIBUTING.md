# Contributing to gdb-visualizer

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/sem-daaboul/gdb-visualizer.git
cd gdb-visualizer

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Project Structure

```
gdb-visualizer/
├── gdbviz/                    # Main package
│   ├── __init__.py           # Version, metadata
│   ├── models.py             # Core data models (Graph, Node, Edge)
│   ├── cli.py                # Click CLI entry points
│   ├── exporter.py           # Format exporters (JSON, Mermaid, etc.)
│   └── extractor/            # Extraction backends
│       ├── __init__.py       # Base class + registry
│       ├── arcpy_extractor.py    # Full extraction (ArcGIS)
│       └── ogr_extractor.py      # Basic extraction (GDAL)
├── examples/                 # Sample data
├── tests/                    # Unit tests
├── static/                   # Phase 2: D3.js assets
├── pyproject.toml            # Package config
└── README.md
```

## Adding a New Export Format

1. Create a new class in `gdbviz/exporter.py`
2. Inherit from `BaseExporter`
3. Decorate with `@register_exporter`
4. Implement `export(graph: Graph) -> str`
5. Add tests in `tests/test_exporters.py`
6. Update `README.md` format table

## Adding a New Extractor

1. Create a new file in `gdbviz/extractor/`
2. Inherit from `BaseExtractor`
3. Decorate with `@register_extractor`
4. Implement `is_available()` and `extract(gdb_path) -> Graph`
5. Add tests (mock arcpy/GDAL if needed)

## Code Style

- **Ruff** for linting (line length: 100)
- **Type hints** — use `from __future__ import annotations`
- **Dataclasses** for models (not Pydantic, not attrs)
- **No external dependencies** beyond click + rich (plus arcpy/GDAL as optional)

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=gdbviz --cov-report=term-missing

# Run specific test file
pytest tests/test_models.py
```

Tests are organized by module:
- `test_models.py` — Graph, Node, Edge data models
- `test_exporters.py` — Format exporters
- `test_cli.py` — CLI commands (Phase 1)

## Pull Request Guidelines

1. Keep PRs focused — one feature or fix per PR
2. Add tests for new functionality
3. Update README if adding user-facing features
4. Run `pytest` before submitting
5. Write clear commit messages

## Reporting Issues

When reporting a bug, please include:
- Python version
- ArcGIS Pro version (if using arcpy extractor)
- GDAL version (if using OGR extractor)
- Full error traceback
- Minimal reproduction steps

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
