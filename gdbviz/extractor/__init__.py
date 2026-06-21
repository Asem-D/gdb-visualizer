"""
Extractor interface and registry.

Extractors read a geodatabase and produce a Graph.
Each backend (arcpy, GDAL) implements BaseExtractor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from gdbviz.models import Graph


class BaseExtractor(ABC):
    """
    Abstract base for geodatabase schema extractors.

    Subclasses must implement `extract()` and `is_available()`.
    """

    name: str = "base"
    description: str = ""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return True if this extractor's dependencies are installed."""
        ...

    @abstractmethod
    def extract(self, gdb_path: str | Path) -> Graph:
        """
        Extract the schema from a geodatabase.

        Args:
            gdb_path: Path to the .gdb directory.

        Returns:
            A fully populated Graph model.

        Raises:
            FileNotFoundError: If gdb_path does not exist.
            RuntimeError: If extraction fails.
        """
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_extractors: dict[str, type[BaseExtractor]] = {}


def register_extractor(cls: type[BaseExtractor]) -> type[BaseExtractor]:
    """Register an extractor class by its `name` attribute."""
    _extractors[cls.name] = cls
    return cls


def get_extractor(name: str) -> BaseExtractor:
    """Instantiate a registered extractor by name."""
    if name not in _extractors:
        available = list(_extractors.keys())
        raise ValueError(
            f"Unknown extractor '{name}'. Available: {available}"
        )
    return _extractors[name]()


def list_extractors() -> list[dict[str, str | bool]]:
    """List all registered extractors and their availability."""
    result = []
    for name, cls in _extractors.items():
        result.append({
            "name": name,
            "description": cls.description,
            "available": cls.is_available(),
        })
    return result


def auto_select_extractor() -> BaseExtractor:
    """
    Pick the best available extractor automatically.

    Prefers arcpy (full extraction) over GDAL (basic).
    Raises RuntimeError if nothing is available.
    """
    # Try arcpy first (full extraction)
    if "arcpy" in _extractors and _extractors["arcpy"].is_available():
        return _extractors["arcpy"]()

    # Fall back to GDAL (basic extraction)
    if "ogr" in _extractors and _extractors["ogr"].is_available():
        return _extractors["ogr"]()

    raise RuntimeError(
        "No extraction backend available.\n"
        "Install ArcGIS Pro (for full extraction) or "
        "GDAL/OGR (for basic extraction).\n"
        "See: https://github.com/sem-daaboul/gdb-visualizer#installation"
    )
