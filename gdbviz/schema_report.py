"""
Schema Report generator — wraps Esri's Generate Schema Report GP tool.

Produces a self-contained HTML report (or Excel) describing a geodatabase's
complete schema: domains, subtypes, attribute rules, dataset schemas,
relationship classes, and more.

Requires ArcGIS Pro (arcpy).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


class SchemaReportError(Exception):
    """Raised when report generation fails."""


class SchemaReportGenerator:
    """Generate Esri Schema Report via arcpy.management.SchemaReport()."""

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """Return True if arcpy is importable."""
        try:
            import arcpy  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate(
        gdb_path: str | Path,
        output_path: str | Path,
        output_format: str = "html",
        include_dataset_properties: bool = True,
        include_spatial_reference: bool = True,
        include_subtypes: bool = True,
        include_domains: bool = True,
        include_attribute_rules: bool = True,
        include_relationship_classes: bool = True,
    ) -> Path:
        """
        Run the Esri Generate Schema Report geoprocessing tool.

        Parameters
        ----------
        gdb_path:
            Path to the .gdb geodatabase.
        output_path:
            Where to write the report file.  Parent directories are created
            automatically.
        output_format:
            ``"html"`` (default) or ``"excel"``.  Excel requires openpyxl.
        include_dataset_properties ... include_relationship_classes:
            Toggle sections in the report.

        Returns
        -------
        Path
            Absolute path to the generated report file.

        Raises
        ------
        SchemaReportError
            If arcpy is missing or the GP tool fails.
        FileNotFoundError
            If gdb_path does not exist.
        ValueError
            If gdb_path is not a .gdb or output_format is unsupported.
        """
        # -- Validate inputs -----------------------------------------------
        gdb_path = Path(gdb_path)
        if not gdb_path.exists():
            raise FileNotFoundError(f"Geodatabase not found: {gdb_path}")
        if not gdb_path.suffix == ".gdb":
            raise ValueError(f"Not a File Geodatabase (.gdb): {gdb_path}")

        output_path = Path(output_path)
        output_format = output_format.lower()
        if output_format not in ("html", "excel", "xlsx"):
            raise ValueError(
                f"Unsupported output format '{output_format}'. "
                "Use 'html' or 'excel'."
            )

        # If excel was passed as "excel", fix extension
        if output_format == "excel":
            output_format = "xlsx"

        # Ensure correct extension on output path
        expected_ext = ".html" if output_format == "html" else ".xlsx"
        if output_path.suffix.lower() != expected_ext:
            output_path = output_path.with_suffix(expected_ext)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # -- Check arcpy ---------------------------------------------------
        if not SchemaReportGenerator.is_available():
            raise SchemaReportError(
                "arcpy is not available.  "
                "The Esri Schema Report requires ArcGIS Pro.\n"
                "Install ArcGIS Pro or run in the ArcGIS Pro Python environment."
            )

        import arcpy

        # -- Build GP tool arguments ---------------------------------------
        gdb_str = str(gdb_path)
        out_str = str(output_path)

        # SchemaReport signature (ArcGIS Pro 3.x):
        #   SchemaReport(in_workspace, out_location, {report_format},
        #                {dataset_properties}, {spatial_reference},
        #                {subtypes}, {domains}, {attribute_rules},
        #                {relationship_classes})
        try:
            arcpy.management.SchemaReport(
                in_workspace=gdb_str,
                out_location=out_str,
                report_format=output_format.upper() if output_format == "html" else "EXCEL",
                dataset_properties="NO_DATASET_PROPERTIES" if not include_dataset_properties else "DATASET_PROPERTIES",
                spatial_reference="NO_SPATIAL_REFERENCE" if not include_spatial_reference else "SPATIAL_REFERENCE",
                subtypes="NO_SUBTYPES" if not include_subtypes else "SUBTYPES",
                domains="NO_DOMAINS" if not include_domains else "DOMAINS",
                attribute_rules="NO_ATTRIBUTE_RULES" if not include_attribute_rules else "ATTRIBUTE_RULES",
                relationship_classes="NO_RELATIONSHIP_CLASSES" if not include_relationship_classes else "RELATIONSHIP_CLASSES",
            )
        except arcpy.ExecuteError:
            raise SchemaReportError(
                f"ArcGIS GP tool failed:\n{arcpy.GetMessages(2)}"
            )
        except Exception as exc:
            raise SchemaReportError(
                f"Unexpected error running SchemaReport: {exc}"
            )

        # -- Verify output exists ------------------------------------------
        if not output_path.exists():
            # SchemaReport sometimes writes to a subdirectory
            # Check common alternative locations
            alt = output_path.parent / output_path.name
            if alt.exists():
                output_path = alt
            else:
                raise SchemaReportError(
                    f"Report generation completed but output file not found at: {output_path}\n"
                    f"Check the output directory for the generated file."
                )

        return output_path.resolve()

    # ------------------------------------------------------------------
    # Convenience: generate both HTML + Excel
    # ------------------------------------------------------------------

    @classmethod
    def generate_both(
        cls,
        gdb_path: str | Path,
        output_dir: str | Path,
        prefix: str = "schema_report",
        **kwargs,
    ) -> dict[str, Path]:
        """
        Generate both HTML and Excel reports.

        Returns dict with keys "html" and "excel" mapped to output Paths.
        Only includes formats that succeeded.
        """
        output_dir = Path(output_dir)
        results = {}

        try:
            html_path = cls.generate(
                gdb_path,
                output_dir / f"{prefix}.html",
                output_format="html",
                **kwargs,
            )
            results["html"] = html_path
        except SchemaReportError:
            pass

        try:
            xlsx_path = cls.generate(
                gdb_path,
                output_dir / f"{prefix}.xlsx",
                output_format="excel",
                **kwargs,
            )
            results["excel"] = xlsx_path
        except SchemaReportError:
            pass

        return results
