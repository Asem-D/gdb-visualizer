"""
GDAL/OGR fallback extractor — basic schema extraction without ArcGIS.

Uses GDAL's OpenFileGDB driver (read-only) to extract:
- Feature classes with geometry types
- Tables
- Fields and their types

Does NOT capture: relationship classes, domains, topology, subtypes.
These require arcpy and are noted in the output metadata.
"""

from __future__ import annotations

from pathlib import Path

from gdbviz.models import (
    Graph, Node, Edge,
    NodeType, EdgeType, GeometryType, FieldType,
    Field,
)
from gdbviz.extractor import BaseExtractor, register_extractor


def _map_ogr_field_type(ogr_type: int) -> FieldType:
    """Map OGR field type integer to our FieldType enum."""
    try:
        from osgeo import ogr
        mapping = {
            ogr.OFTInteger: FieldType.LONG,
            ogr.OFTInteger64: FieldType.LONG,
            ogr.OFTReal: FieldType.DOUBLE,
            ogr.OFTString: FieldType.TEXT,
            ogr.OFTDate: FieldType.DATE,
            ogr.OFTTime: FieldType.DATE,
            ogr.OFTDateTime: FieldType.DATE,
            ogr.OFTBinary: FieldType.BLOB,
            ogr.OFTWideString: FieldType.TEXT,
            ogr.OFTIntegerList: FieldType.LONG,
            ogr.OFTRealList: FieldType.DOUBLE,
            ogr.OFTStringList: FieldType.TEXT,
        }
        return mapping.get(ogr_type, FieldType.TEXT)
    except (ImportError, AttributeError):
        return FieldType.TEXT


def _map_ogr_geom_type(ogr_geom_type: int) -> GeometryType:
    """Map OGR geometry type integer to our GeometryType enum."""
    try:
        from osgeo import ogr
        mapping = {
            ogr.wkbPoint: GeometryType.POINT,
            ogr.wkbMultiPoint: GeometryType.MULTIPOINT,
            ogr.wkbLineString: GeometryType.POLYLINE,
            ogr.wkbMultiLineString: GeometryType.POLYLINE,
            ogr.wkbPolygon: GeometryType.POLYGON,
            ogr.wkbMultiPolygon: GeometryType.POLYGON,
            ogr.wkbNone: GeometryType.NONE,
            ogr.wkbUnknown: GeometryType.UNKNOWN,
        }
        return mapping.get(ogr_geom_type, GeometryType.UNKNOWN)
    except (ImportError, AttributeError):
        return GeometryType.UNKNOWN


@register_extractor
class OgrExtractor(BaseExtractor):
    """Basic schema extraction using GDAL/OGR (no ArcGIS required)."""

    name = "ogr"
    description = "Basic extraction without ArcGIS (feature classes, fields, geometry types only)"

    @classmethod
    def is_available(cls) -> bool:
        try:
            from osgeo import ogr, gdal  # noqa: F401
            # Check if the OpenFileGDB driver is available
            driver = ogr.GetDriverByName("OpenFileGDB")
            return driver is not None
        except ImportError:
            return False

    def extract(self, gdb_path: str | Path) -> Graph:
        from osgeo import ogr, osr

        gdb_path = Path(gdb_path)
        if not gdb_path.exists():
            raise FileNotFoundError(f"Geodatabase not found: {gdb_path}")

        gdb_str = str(gdb_path)
        gdb_name = gdb_path.stem

        # Open with OpenFileGDB driver (read-only, but no ArcGIS needed)
        driver = ogr.GetDriverByName("OpenFileGDB")
        ds = driver.Open(gdb_str, 0)  # 0 = read-only
        if ds is None:
            raise RuntimeError(
                f"Failed to open geodatabase: {gdb_path}\n"
                "Ensure the path is a valid File Geodatabase."
            )

        graph = Graph(
            name=gdb_name,
            path=gdb_str,
            metadata={
                "extractor": "ogr",
                "note": "Basic extraction — relationship classes, domains, topology, "
                        "and subtypes require the arcpy extractor.",
            },
        )

        try:
            layer_count = ds.GetLayerCount()

            for i in range(layer_count):
                layer = ds.GetLayerByIndex(i)
                layer_name = layer.GetName()
                geom_type = layer.GetGeomType()
                layer_defn = layer.GetLayerDefn()

                # Determine if this is a spatial layer or a table
                is_spatial = geom_type != ogr.wkbNone

                if is_spatial:
                    node_id = f"feature_class://{gdb_str}\\{layer_name}"
                    node_type = NodeType.FEATURE_CLASS
                else:
                    node_id = f"table://{gdb_str}\\{layer_name}"
                    node_type = NodeType.TABLE

                # Extract fields
                fields = []
                for j in range(layer_defn.GetFieldCount()):
                    field_defn = layer_defn.GetFieldDefn(j)
                    field = Field(
                        name=field_defn.GetName(),
                        field_type=_map_ogr_field_type(field_defn.GetType()),
                        alias=field_defn.GetName() or "",
                        length=field_defn.GetWidth() if field_defn.GetWidth() > 0 else None,
                        is_nullable=field_defn.IsNullable(),
                        is_oid=(field_defn.GetName() == "OBJECTID"),
                        is_shape=False,
                    )
                    fields.append(field)

                # Feature count
                feature_count = layer.GetFeatureCount()

                # Spatial reference
                srs = layer.GetSpatialRef()
                sr_name = srs.GetAuthorityCode(None) if srs else "Unknown"

                properties = {
                    "field_count": len(fields),
                    "fields": [f.to_dict() for f in fields],
                    "feature_count": feature_count,
                    "spatial_reference": sr_name,
                }

                if is_spatial:
                    properties["geometry_type"] = _map_ogr_geom_type(geom_type).value
                    # Try to get the shape field name
                    for j in range(layer_defn.GetFieldCount()):
                        fd = layer_defn.GetFieldDefn(j)
                        if fd.GetType() == ogr.OFTBinary:
                            properties["shape_field"] = fd.GetName()
                            break
                else:
                    properties["geometry_type"] = "None"

                graph.add_node(Node(
                    id=node_id,
                    name=layer_name,
                    node_type=node_type,
                    properties=properties,
                ))

        finally:
            ds = None  # Close the dataset

        return graph
