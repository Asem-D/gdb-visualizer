"""
Tests for gdbviz.schema_report — Esri Schema Report generator.

All tests mock arcpy so they run in any environment.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Tests: is_available
# ---------------------------------------------------------------------------

class TestIsAvailable:
    def test_available_when_arcpy_exists(self):
        with patch.dict("sys.modules", {"arcpy": MagicMock()}):
            from gdbviz.schema_report import SchemaReportGenerator
            assert SchemaReportGenerator.is_available() is True

    def test_unavailable_when_no_arcpy(self):
        with patch.dict("sys.modules", {"arcpy": None}):
            import importlib
            import gdbviz.schema_report as sr
            importlib.reload(sr)
            assert sr.SchemaReportGenerator.is_available() is False


# ---------------------------------------------------------------------------
# Tests: Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_gdb_not_found(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator
        with pytest.raises(FileNotFoundError, match="not found"):
            SchemaReportGenerator.generate(
                gdb_path=tmp_path / "missing.gdb",
                output_path=tmp_path / "report.html",
            )

    def test_not_a_gdb(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator
        fake_gdb = tmp_path / "not_a_gdb"
        fake_gdb.mkdir()
        with pytest.raises(ValueError, match="Not a File Geodatabase"):
            SchemaReportGenerator.generate(
                gdb_path=fake_gdb,
                output_path=tmp_path / "report.html",
            )

    def test_unsupported_format(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator
        fake_gdb = tmp_path / "test.gdb"
        fake_gdb.mkdir()
        with pytest.raises(ValueError, match="Unsupported output format"):
            SchemaReportGenerator.generate(
                gdb_path=fake_gdb,
                output_path=tmp_path / "report.pdf",
                output_format="pdf",
            )


# ---------------------------------------------------------------------------
# Tests: ArcPy not available
# ---------------------------------------------------------------------------

class TestArcPyMissing:
    def test_raises_when_arcpy_unavailable(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator, SchemaReportError
        fake_gdb = tmp_path / "test.gdb"
        fake_gdb.mkdir()

        with patch.object(SchemaReportGenerator, "is_available", return_value=False):
            with pytest.raises(SchemaReportError, match="arcpy is not available"):
                SchemaReportGenerator.generate(
                    gdb_path=fake_gdb,
                    output_path=tmp_path / "report.html",
                )


# ---------------------------------------------------------------------------
# Tests: Successful generation (mocked arcpy)
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_html_generation(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator

        fake_gdb = tmp_path / "test.gdb"
        fake_gdb.mkdir()
        out_path = tmp_path / "report.html"

        mock_arcpy = MagicMock()
        # Simulate successful run — file appears after GP call
        def fake_schema_report(**kwargs):
            Path(kwargs.get("out_location", out_path)).touch()

        mock_arcpy.management.SchemaReport.side_effect = fake_schema_report

        with patch.dict("sys.modules", {"arcpy": mock_arcpy}):
            result = SchemaReportGenerator.generate(
                gdb_path=fake_gdb,
                output_path=out_path,
                output_format="html",
            )
            assert result.exists()
            assert result.suffix == ".html"

    def test_excel_generation(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator

        fake_gdb = tmp_path / "test.gdb"
        fake_gdb.mkdir()
        out_path = tmp_path / "report.xlsx"

        mock_arcpy = MagicMock()
        def fake_schema_report(**kwargs):
            Path(kwargs.get("out_location", out_path)).touch()

        mock_arcpy.management.SchemaReport.side_effect = fake_schema_report

        with patch.dict("sys.modules", {"arcpy": mock_arcpy}):
            result = SchemaReportGenerator.generate(
                gdb_path=fake_gdb,
                output_path=out_path,
                output_format="excel",
            )
            assert result.exists()
            assert result.suffix == ".xlsx"

    def test_creates_parent_dirs(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator

        fake_gdb = tmp_path / "test.gdb"
        fake_gdb.mkdir()
        out_path = tmp_path / "subdir" / "reports" / "report.html"

        mock_arcpy = MagicMock()
        def fake_schema_report(**kwargs):
            Path(kwargs.get("out_location", out_path)).parent.mkdir(parents=True, exist_ok=True)
            Path(kwargs.get("out_location", out_path)).touch()

        mock_arcpy.management.SchemaReport.side_effect = fake_schema_report

        with patch.dict("sys.modules", {"arcpy": mock_arcpy}):
            result = SchemaReportGenerator.generate(
                gdb_path=fake_gdb,
                output_path=out_path,
            )
            assert result.exists()

    def test_gp_tool_failure(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator, SchemaReportError

        fake_gdb = tmp_path / "test.gdb"
        fake_gdb.mkdir()

        mock_arcpy = MagicMock()
        mock_arcpy.ExecuteError = type("ExecuteError", (Exception,), {})
        mock_arcpy.management.SchemaReport.side_effect = mock_arcpy.ExecuteError("GP failed")
        mock_arcpy.GetMessages.return_value = "ERROR 000001: GP failed"

        with patch.dict("sys.modules", {"arcpy": mock_arcpy}):
            with pytest.raises(SchemaReportError, match="GP tool failed"):
                SchemaReportGenerator.generate(
                    gdb_path=fake_gdb,
                    output_path=tmp_path / "report.html",
                )


# ---------------------------------------------------------------------------
# Tests: generate_both
# ---------------------------------------------------------------------------

class TestGenerateBoth:
    def test_returns_both_formats(self, tmp_path):
        from gdbviz.schema_report import SchemaReportGenerator

        fake_gdb = tmp_path / "test.gdb"
        fake_gdb.mkdir()

        mock_arcpy = MagicMock()
        def fake_schema_report(**kwargs):
            Path(kwargs.get("out_location")).touch()

        mock_arcpy.management.SchemaReport.side_effect = fake_schema_report

        with patch.dict("sys.modules", {"arcpy": mock_arcpy}):
            results = SchemaReportGenerator.generate_both(
                gdb_path=fake_gdb,
                output_dir=tmp_path / "reports",
            )
            assert "html" in results
            assert "excel" in results
            assert results["html"].exists()
            assert results["excel"].exists()
