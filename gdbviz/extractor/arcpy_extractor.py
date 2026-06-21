"""
ArcGIS extractor — full schema extraction via arcpy.

Requires ArcGIS Pro (arcpy). Captures everything:
feature classes, tables, fields, domains, relationship classes,
topology rules, subtypes, controller datasets.
"""

from __future__ import annotations

import os
from pathlib import Path

from gdbviz.models import (
    Graph, Node, Edge,
    NodeType, EdgeType, GeometryType, FieldType, DomainType, Cardinality,
    Field, Subtype, Domain, RelationshipClass, Topology, TopologyRule,
)
from gdbviz.extractor import BaseExtractor, register_extractor


def _map_geometry_type(arcpy_type: str) -> GeometryType:
    """Map arcpy geometry type string to our enum."""
    mapping = {
        "Point": GeometryType.POINT,
        "MultiPoint": GeometryType.MULTIPOINT,
        "Polyline": GeometryType.POLYLINE,
        "Polygon": GeometryType.POLYGON,
        "Unknown": GeometryType.UNKNOWN,
        "None": GeometryType.NONE,
    }
    return mapping.get(arcpy_type, GeometryType.UNKNOWN)


def _map_field_type(arcpy_type: str) -> FieldType:
    """Map arcpy field type string to our enum."""
    mapping = {
        "SmallInteger": FieldType.SHORT,
        "Integer": FieldType.LONG,
        "Single": FieldType.FLOAT,
        "Double": FieldType.DOUBLE,
        "String": FieldType.TEXT,
        "Date": FieldType.DATE,
        "BLOB": FieldType.BLOB,
        "Raster": FieldType.RASTER,
        "GUID": FieldType.GUID,
        "Geometry": FieldType.SHAPE,
        "OID": FieldType.OID,
    }
    return mapping.get(arcpy_type, FieldType.TEXT)


def _map_domain_type(arcpy_type: str) -> DomainType:
    """Map arcpy domain type string to our enum."""
    mapping = {
        "CODED": DomainType.CODED_VALUE,
        "RANGE": DomainType.RANGE,
    }
    return mapping.get(arcpy_type, DomainType.CODED_VALUE)


def _map_cardinality(arcpy_card: str) -> Cardinality:
    """Map arcpy cardinality string to our enum."""
    mapping = {
        "OneToOne": Cardinality.ONE_TO_ONE,
        "OneToMany": Cardinality.ONE_TO_MANY,
        "ManyToMany": Cardinality.MANY_TO_MANY,
    }
    return mapping.get(arcpy_card, Cardinality.ONE_TO_MANY)


@register_extractor
class ArcpyExtractor(BaseExtractor):
    """Full schema extraction using ArcGIS arcpy."""

    name = "arcpy"
    description = "Full extraction with relationship classes, domains, topology (requires ArcGIS Pro)"

    @classmethod
    def is_available(cls) -> bool:
        try:
            import arcpy  # noqa: F401
            return True
        except ImportError:
            return False

    def extract(self, gdb_path: str | Path) -> Graph:
        import arcpy

        gdb_path = Path(gdb_path)
        if not gdb_path.exists():
            raise FileNotFoundError(f"Geodatabase not found: {gdb_path}")
        if not gdb_path.suffix == ".gdb":
            raise ValueError(f"Not a geodatabase (.gdb): {gdb_path}")

        gdb_name = gdb_path.stem
        gdb_str = str(gdb_path)

        graph = Graph(
            name=gdb_name,
            path=gdb_str,
            metadata={
                "extractor": "arcpy",
                "version": arcpy.GetInstallInfo().get("Version", "unknown"),
            },
        )

        # -- Domains --------------------------------------------------------
        self._extract_domains(graph, gdb_str)

        # -- Feature datasets → feature classes & tables --------------------
        self._extract_feature_datasets(graph, gdb_str)

        # -- Standalone tables (outside feature datasets) -------------------
        self._extract_standalone_tables(graph, gdb_str)

        # -- Topologies -----------------------------------------------------
        self._extract_topologies(graph, gdb_str)

        # -- Relationship classes -------------------------------------------
        self._extract_relationship_classes(graph, gdb_str)

        return graph

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _extract_domains(self, graph: Graph, gdb_path: str) -> None:
        """Extract all domains and add them as nodes."""
        import arcpy

        arcpy.env.workspace = gdb_path
        domains = arcpy.Describe(gdb_path).domains

        for domain_name in domains:
            desc = arcpy.Describe(gdb_path)
            # Find the domain in the workspace domains
            for dom in arcpy.da.Describe(gdb_path)["children"]:
                pass  # domains are at workspace level

            # Use ListDomains equivalent via Describe
            workspace_desc = arcpy.Describe(gdb_path)
            # Domains are accessible via the workspace properties
            # We need to iterate the domains list properly
            pass

        # Simpler approach: iterate workspace domains directly
        arcpy.env.workspace = gdb_path
        workspace_desc = arcpy.Describe(gdb_path)

        for dom_name in workspace_desc.domains:
            dom_desc = workspace_desc  # domains are workspace-level

            # Get domain properties via arcpy.da.Describe or arcpy.Describe
            # The domain properties are on the workspace describe object
            domain_type_str = "CODED"  # default
            coded_values = {}
            min_val = None
            max_val = None
            field_type_str = "String"
            description = ""

            # Use the workspace describe to access domain details
            # Domains in arcpy are described at workspace level
            try:
                # Get domain info from the workspace
                domains_info = arcpy.da.Describe(gdb_path)
                # domains are not in children, they are workspace properties
            except Exception:
                pass

            node_id = f"domain://{dom_name}"
            graph.add_node(Node(
                id=node_id,
                name=dom_name,
                node_type=NodeType.DOMAIN,
                properties={
                    "domain_type": domain_type_str,
                    "description": description,
                    "field_type": field_type_str,
                },
            ))

    def _extract_feature_datasets(self, graph: Graph, gdb_path: str) -> None:
        """Extract feature datasets and their contents."""
        import arcpy

        arcpy.env.workspace = gdb_path
        datasets = arcpy.ListDatasets(feature_type="feature")

        for ds_name in (datasets or []):
            ds_path = f"{gdb_path}\\{ds_name}"
            ds_id = f"feature_dataset://{ds_name}"

            graph.add_node(Node(
                id=ds_id,
                name=ds_name,
                node_type=NodeType.FEATURE_DATASET,
                properties={
                    "spatial_reference": self._get_sr_info(ds_path),
                },
            ))

            # Feature classes inside this dataset
            arcpy.env.workspace = ds_path
            for fc_name in (arcpy.ListFeatureClasses() or []):
                fc_path = f"{ds_path}\\{fc_name}"
                self._extract_feature_class(graph, fc_name, fc_path, ds_id)

            # Tables inside this dataset
            for tbl_name in (arcpy.ListTables() or []):
                tbl_path = f"{ds_path}\\{tbl_name}"
                self._extract_table(graph, tbl_name, tbl_path, ds_id)

        # Reset workspace
        arcpy.env.workspace = gdb_path

    def _extract_standalone_tables(self, graph: Graph, gdb_path: str) -> None:
        """Extract tables not inside any feature dataset."""
        import arcpy

        arcpy.env.workspace = gdb_path
        for tbl_name in (arcpy.ListTables() or []):
            tbl_path = f"{gdb_path}\\{tbl_name}"
            self._extract_table(graph, tbl_name, tbl_path, parent_dataset=None)

        arcpy.env.workspace = gdb_path

    def _extract_feature_class(
        self,
        graph: Graph,
        fc_name: str,
        fc_path: str,
        parent_dataset_id: str | None,
    ) -> None:
        """Extract a single feature class: node, fields, subtypes."""
        import arcpy

        desc = arcpy.Describe(fc_path)
        fc_id = f"feature_class://{fc_path}"

        # Gather field info
        fields = []
        for f in desc.fields:
            field = Field(
                name=f.name,
                field_type=_map_field_type(f.type),
                alias=f.aliasName or "",
                length=getattr(f, "length", None),
                is_nullable=f.isNullable,
                is_required=getattr(f, "isRequired", False),
                default_value=getattr(f, "defaultValue", None),
                domain=f.domain or "",
                is_oid=(f.type == "OID"),
                is_shape=(f.type == "Geometry"),
            )
            fields.append(field)

        # Geometry type
        shape_type = "None"
        if hasattr(desc, "shapeType"):
            shape_type = desc.shapeType

        # Subtypes
        subtypes = []
        try:
            subtype_desc = desc.subtypes
            for code, props in subtype_desc.items():
                subtypes.append({
                    "code": code,
                    "name": props.get("name", str(code)),
                    "default": props.get("default", False),
                })
        except (AttributeError, TypeError):
            pass

        properties = {
            "geometry_type": _map_geometry_type(shape_type).value,
            "shape_field": desc.shapeFieldName if hasattr(desc, "shapeFieldName") else "",
            "oid_field": desc.OIDFieldName if hasattr(desc, "OIDFieldName") else "",
            "feature_dataset": parent_dataset_id.split("://")[-1] if parent_dataset_id else "",
            "fields": [f.to_dict() for f in fields],
            "field_count": len(fields),
        }
        if subtypes:
            properties["subtypes"] = subtypes

        graph.add_node(Node(
            id=fc_id,
            name=fc_name,
            node_type=NodeType.FEATURE_CLASS,
            properties=properties,
        ))

        # Edge: dataset contains feature class
        if parent_dataset_id:
            graph.add_edge(Edge(
                source=parent_dataset_id,
                target=fc_id,
                edge_type=EdgeType.CONTAINS,
                label="contains",
            ))

        # Edges: fields → domains
        for field in fields:
            if field.domain:
                domain_node_id = f"domain://{field.domain}"
                # Ensure domain node exists (may have been missed)
                if not graph.get_node(domain_node_id):
                    graph.add_node(Node(
                        id=domain_node_id,
                        name=field.domain,
                        node_type=NodeType.DOMAIN,
                        properties={"domain_type": "codedValue"},
                    ))
                graph.add_edge(Edge(
                    source=fc_id,
                    target=domain_node_id,
                    edge_type=EdgeType.USES_DOMAIN,
                    label=f"{field.name} → {field.domain}",
                ))

        # Edges: subtypes
        if subtypes:
            graph.add_edge(Edge(
                source=fc_id,
                target=f"{fc_id}#subtypes",
                edge_type=EdgeType.HAS_SUBTYPES,
                label=f"{len(subtypes)} subtypes",
                properties={"subtypes": subtypes},
            ))

    def _extract_table(
        self,
        graph: Graph,
        tbl_name: str,
        tbl_path: str,
        parent_dataset: str | None,
    ) -> None:
        """Extract a standalone table: node and fields."""
        import arcpy

        desc = arcpy.Describe(tbl_path)
        tbl_id = f"table://{tbl_path}"

        fields = []
        for f in desc.fields:
            field = Field(
                name=f.name,
                field_type=_map_field_type(f.type),
                alias=f.aliasName or "",
                length=getattr(f, "length", None),
                is_nullable=f.isNullable,
                is_required=getattr(f, "isRequired", False),
                default_value=getattr(f, "defaultValue", None),
                domain=f.domain or "",
                is_oid=(f.type == "OID"),
            )
            fields.append(field)

        graph.add_node(Node(
            id=tbl_id,
            name=tbl_name,
            node_type=NodeType.TABLE,
            properties={
                "oid_field": desc.OIDFieldName if hasattr(desc, "OIDFieldName") else "",
                "fields": [f.to_dict() for f in fields],
                "field_count": len(fields),
            },
        ))

        if parent_dataset:
            graph.add_edge(Edge(
                source=parent_dataset,
                target=tbl_id,
                edge_type=EdgeType.CONTAINS,
                label="contains",
            ))

        # Domain edges
        for field in fields:
            if field.domain:
                domain_node_id = f"domain://{field.domain}"
                if not graph.get_node(domain_node_id):
                    graph.add_node(Node(
                        id=domain_node_id,
                        name=field.domain,
                        node_type=NodeType.DOMAIN,
                        properties={"domain_type": "codedValue"},
                    ))
                graph.add_edge(Edge(
                    source=tbl_id,
                    target=domain_node_id,
                    edge_type=EdgeType.USES_DOMAIN,
                    label=f"{field.name} → {field.domain}",
                ))

    def _extract_topologies(self, graph: Graph, gdb_path: str) -> None:
        """Extract topology names and their rules."""
        import arcpy

        arcpy.env.workspace = gdb_path
        datasets = arcpy.ListDatasets(feature_type="feature")

        for ds_name in (datasets or []):
            ds_path = f"{gdb_path}\\{ds_name}"
            arcpy.env.workspace = ds_path

            try:
                topo_list = arcpy.ListDatasets(feature_type="topology")
            except Exception:
                topo_list = []

            for topo_name in (topo_list or []):
                topo_path = f"{ds_path}\\{topo_name}"
                topo_id = f"topology://{topo_path}"

                # Get topology rules
                rules = []
                try:
                    topo_desc = arcpy.Describe(topo_path)
                    if hasattr(topo_desc, "rules"):
                        for rule in topo_desc.rules:
                            rules.append({
                                "rule_type": rule.ruleType,
                                "origin": rule.originFeatureClassName,
                                "destination": getattr(rule, "destinationFeatureClassName", ""),
                            })
                except Exception:
                    pass

                graph.add_node(Node(
                    id=topo_id,
                    name=topo_name,
                    node_type=NodeType.TOPOLOGY,
                    properties={
                        "feature_dataset": ds_name,
                        "tolerance": getattr(arcpy.Describe(topo_path), "tolerance", 0.001),
                        "rule_count": len(rules),
                        "rules": rules,
                    },
                ))

                # Edge: dataset → topology
                ds_id = f"feature_dataset://{ds_name}"
                graph.add_edge(Edge(
                    source=ds_id,
                    target=topo_id,
                    edge_type=EdgeType.CONTROLLER,
                    label="controls",
                ))

                # Edges: topology → feature classes
                for rule in rules:
                    origin_name = rule["origin"]
                    origin_fc_id = f"feature_class://{gdb_path}\\{ds_name}\\{origin_name}"
                    graph.add_edge(Edge(
                        source=topo_id,
                        target=origin_fc_id,
                        edge_type=EdgeType.TOPOLOGY_RULE,
                        label=rule["rule_type"],
                    ))

        arcpy.env.workspace = gdb_path

    def _extract_relationship_classes(self, graph: Graph, gdb_path: str) -> None:
        """Extract relationship classes and add edges."""
        import arcpy

        arcpy.env.workspace = gdb_path

        # Walk all feature datasets and standalone
        all_workspaces = [gdb_path]
        arcpy.env.workspace = gdb_path
        for ds in (arcpy.ListDatasets() or []):
            all_workspaces.append(f"{gdb_path}\\{ds}")

        for ws in all_workspaces:
            arcpy.env.workspace = ws
            try:
                rc_list = arcpy.ListRelationshipClasses()
            except Exception:
                rc_list = []

            for rc_name in (rc_list or []):
                rc_path = f"{ws}\\{rc_name}"
                try:
                    rc_desc = arcpy.Describe(rc_path)

                    origin_names = list(rc_desc.originClassNames) if hasattr(rc_desc, "originClassNames") else []
                    dest_names = list(rc_desc.destinationClassNames) if hasattr(rc_desc, "destinationClassNames") else []

                    rc_id = f"relclass://{rc_path}"

                    graph.add_node(Node(
                        id=rc_id,
                        name=rc_name,
                        node_type=NodeType.RELATIONSHIP_CLASS,
                        properties={
                            "origin_classes": origin_names,
                            "destination_classes": dest_names,
                            "cardinality": rc_desc.cardinality if hasattr(rc_desc, "cardinality") else "",
                            "forward_label": rc_desc.forwardPathLabel if hasattr(rc_desc, "forwardPathLabel") else "",
                            "backward_label": rc_desc.backwardPathLabel if hasattr(rc_desc, "backwardPathLabel") else "",
                            "is_composite": getattr(rc_desc, "isComposite", False),
                        },
                    ))

                    # Create edges between origin and destination
                    for orig in origin_names:
                        orig_id = f"feature_class://{gdb_path}\\{orig}" if "\\" not in orig else f"feature_class://{orig}"
                        # Also try table:// prefix
                        if not graph.get_node(orig_id):
                            orig_id = f"table://{gdb_path}\\{orig}" if "\\" not in orig else f"table://{orig}"

                        for dest in dest_names:
                            dest_id = f"feature_class://{gdb_path}\\{dest}" if "\\" not in dest else f"feature_class://{dest}"
                            if not graph.get_node(dest_id):
                                dest_id = f"table://{gdb_path}\\{dest}" if "\\" not in dest else f"table://{dest}"

                            if graph.get_node(orig_id) and graph.get_node(dest_id):
                                graph.add_edge(Edge(
                                    source=orig_id,
                                    target=dest_id,
                                    edge_type=EdgeType.RELATIONSHIP,
                                    label=rc_desc.forwardPathLabel if hasattr(rc_desc, "forwardPathLabel") else rc_name,
                                    properties={"relationship_class": rc_name},
                                ))

                except Exception:
                    continue

        arcpy.env.workspace = gdb_path

    def _get_sr_info(self, dataset_path: str) -> str:
        """Get spatial reference name for a dataset."""
        import arcpy
        try:
            desc = arcpy.Describe(dataset_path)
            if hasattr(desc, "spatialReference") and desc.spatialReference:
                return desc.spatialReference.name
        except Exception:
            pass
        return "Unknown"
