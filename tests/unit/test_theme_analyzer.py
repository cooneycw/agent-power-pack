"""Unit tests for docs/theme_analyzer.py (spec 002, FR-002)."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from agent_power_pack.docs.theme_analyzer import (
    DEFAULT_THEME,
    analyze_theme,
    extract_pptx_theme,
    list_font_files,
    write_theme_yaml,
)


@pytest.mark.unit
class TestListFontFiles:
    def test_empty_dir(self, tmp_path: Path) -> None:
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        assert list_font_files(fonts_dir) == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        assert list_font_files(tmp_path / "nonexistent") == []

    def test_ttf_files_listed(self, tmp_path: Path) -> None:
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        # Create dummy TTF files (no valid name table — fallback to stem)
        (fonts_dir / "Roboto-Regular.ttf").write_bytes(b"\x00" * 20)
        (fonts_dir / "OpenSans-Bold.ttf").write_bytes(b"\x00" * 20)
        result = list_font_files(fonts_dir)
        assert len(result) == 2
        assert result[0]["file"] == "OpenSans-Bold.ttf"
        assert result[0]["family"] == "OpenSans-Bold"  # fallback to stem
        assert result[1]["file"] == "Roboto-Regular.ttf"

    def test_ignores_non_font_files(self, tmp_path: Path) -> None:
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        (fonts_dir / "readme.txt").write_text("not a font")
        (fonts_dir / "logo.png").write_bytes(b"\x89PNG")
        assert list_font_files(fonts_dir) == []

    def test_otf_files_included(self, tmp_path: Path) -> None:
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        (fonts_dir / "Custom.otf").write_bytes(b"\x00" * 20)
        result = list_font_files(fonts_dir)
        assert len(result) == 1
        assert result[0]["file"] == "Custom.otf"


@pytest.mark.unit
class TestExtractPptxTheme:
    def _make_pptx_with_theme(self, path: Path, fonts: bool = True, colors: bool = True) -> None:
        """Create a minimal PPTX with theme XML."""
        ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        theme = ET.Element(f"{{{ns}}}theme")

        if fonts:
            font_scheme = ET.SubElement(theme, f"{{{ns}}}fontScheme", name="TestScheme")
            major = ET.SubElement(font_scheme, f"{{{ns}}}majorFont")
            ET.SubElement(major, f"{{{ns}}}latin", typeface="Arial")
            minor = ET.SubElement(font_scheme, f"{{{ns}}}minorFont")
            ET.SubElement(minor, f"{{{ns}}}latin", typeface="Calibri")

        if colors:
            clr_scheme = ET.SubElement(theme, f"{{{ns}}}clrScheme", name="TestColors")
            dk1 = ET.SubElement(clr_scheme, f"{{{ns}}}dk1")
            ET.SubElement(dk1, f"{{{ns}}}srgbClr", val="1E293B")
            accent1 = ET.SubElement(clr_scheme, f"{{{ns}}}accent1")
            ET.SubElement(accent1, f"{{{ns}}}srgbClr", val="2563EB")

        xml_bytes = ET.tostring(theme, encoding="unicode")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("ppt/theme/theme1.xml", xml_bytes)

    def test_extracts_fonts(self, tmp_path: Path) -> None:
        pptx = tmp_path / "sample.pptx"
        self._make_pptx_with_theme(pptx, fonts=True, colors=False)
        result = extract_pptx_theme(pptx)
        assert len(result["fonts"]) == 2
        assert result["fonts"][0]["role"] == "heading"
        assert result["fonts"][0]["typeface"] == "Arial"
        assert result["fonts"][1]["role"] == "body"
        assert result["fonts"][1]["typeface"] == "Calibri"

    def test_extracts_colors(self, tmp_path: Path) -> None:
        pptx = tmp_path / "sample.pptx"
        self._make_pptx_with_theme(pptx, fonts=False, colors=True)
        result = extract_pptx_theme(pptx)
        assert len(result["colors"]) == 2
        hex_values = [c["hex"] for c in result["colors"]]
        assert "#1E293B" in hex_values
        assert "#2563EB" in hex_values

    def test_handles_bad_zip(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.pptx"
        bad_file.write_bytes(b"not a zip file")
        result = extract_pptx_theme(bad_file)
        assert result["fonts"] == []
        assert result["colors"] == []

    def test_handles_empty_pptx(self, tmp_path: Path) -> None:
        pptx = tmp_path / "empty.pptx"
        with zipfile.ZipFile(pptx, "w") as zf:
            zf.writestr("content.xml", "<root/>")
        result = extract_pptx_theme(pptx)
        assert result["fonts"] == []
        assert result["colors"] == []


@pytest.mark.unit
class TestAnalyzeTheme:
    def test_empty_theme_dir(self, tmp_path: Path) -> None:
        theme_dir = tmp_path / "theme"
        theme_dir.mkdir()
        theme = analyze_theme(theme_dir)
        # Should use defaults with warnings
        assert theme["colors"]["primary"] == DEFAULT_THEME["colors"]["primary"]
        assert len(theme["_warnings"]) > 0

    def test_nonexistent_theme_dir(self, tmp_path: Path) -> None:
        theme = analyze_theme(tmp_path / "nonexistent")
        assert len(theme["_warnings"]) > 0

    def test_with_font_files(self, tmp_path: Path) -> None:
        theme_dir = tmp_path / "theme"
        (theme_dir / "logos").mkdir(parents=True)
        (theme_dir / "samples").mkdir()
        fonts_dir = theme_dir / "fonts"
        fonts_dir.mkdir()
        (fonts_dir / "Roboto.ttf").write_bytes(b"\x00" * 20)
        theme = analyze_theme(theme_dir)
        assert "available" in theme["fonts"]
        assert theme["fonts"]["heading"] == "Roboto"  # fallback to stem

    def test_with_logo_svg(self, tmp_path: Path) -> None:
        theme_dir = tmp_path / "theme"
        logos_dir = theme_dir / "logos"
        logos_dir.mkdir(parents=True)
        (theme_dir / "samples").mkdir()
        (theme_dir / "fonts").mkdir()
        (logos_dir / "logo.svg").write_text("<svg/>")
        theme = analyze_theme(theme_dir)
        assert "logo.svg" in theme["logos"]

    def test_gitkeep_ignored(self, tmp_path: Path) -> None:
        theme_dir = tmp_path / "theme"
        logos_dir = theme_dir / "logos"
        logos_dir.mkdir(parents=True)
        (theme_dir / "samples").mkdir()
        (theme_dir / "fonts").mkdir()
        (logos_dir / ".gitkeep").write_text("")
        theme = analyze_theme(theme_dir)
        assert theme["logos"] == []


@pytest.mark.unit
class TestWriteThemeYaml:
    def test_writes_valid_yaml(self, tmp_path: Path) -> None:
        theme = {
            "colors": {"primary": "#FF0000"},
            "fonts": {"heading": "Arial"},
            "logos": [],
            "layouts": {"slide_width": 1920},
            "_warnings": ["test warning"],
        }
        output = tmp_path / "theme.yaml"
        write_theme_yaml(theme, output)
        content = output.read_text()
        assert "# Theme configuration" in content
        assert "test warning" in content
        assert "primary" in content
        assert "_warnings" not in content  # stripped from YAML data

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        output = tmp_path / "nested" / "dir" / "theme.yaml"
        write_theme_yaml({"colors": {}, "_warnings": []}, output)
        assert output.exists()
