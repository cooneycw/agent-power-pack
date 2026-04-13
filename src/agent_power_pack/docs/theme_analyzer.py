"""Theme inference from docs/theme/ assets (spec 002, FR-002).

Scans logos for dominant colors, fonts for typeface names, and sample
PPTX/PDF files for layout patterns. Writes docs/theme/theme.yaml.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import structlog
from ruamel.yaml import YAML

logger = structlog.get_logger()

# Default theme when no assets are provided (edge case per spec).
DEFAULT_THEME: dict[str, Any] = {
    "colors": {
        "primary": "#2563EB",
        "secondary": "#64748B",
        "accent": "#F59E0B",
        "background": "#FFFFFF",
        "text": "#1E293B",
    },
    "fonts": {
        "heading": "sans-serif",
        "body": "sans-serif",
        "mono": "monospace",
    },
    "logos": [],
    "layouts": {
        "slide_width": 1920,
        "slide_height": 1080,
    },
}


def extract_colors_from_png(path: Path) -> list[str]:
    """Extract dominant colors from a PNG image using PyMuPDF.

    Returns a list of hex color strings (e.g. ['#2563EB', '#FFFFFF']).
    """
    try:
        import fitz  # type: ignore[import-untyped]  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not available, skipping color extraction", path=str(path))
        return []

    try:
        doc = fitz.open(str(path))
        # For single-page image files, fitz opens them as a 1-page document
        if doc.page_count == 0:
            return []
        page = doc[0]
        pix = page.get_pixmap(dpi=72)

        # Sample pixels and count colors
        color_counts: dict[tuple[int, int, int], int] = {}
        samples = pix.samples
        n = pix.n  # components per pixel (3 for RGB, 4 for RGBA)
        stride = pix.stride
        width = pix.width
        height = pix.height

        # Sample every 4th pixel for performance
        step = 4
        for y in range(0, height, step):
            for x in range(0, width, step):
                idx = y * stride + x * n
                if idx + 2 < len(samples):
                    r, g, b = samples[idx], samples[idx + 1], samples[idx + 2]
                    # Skip near-white and near-black (background noise)
                    if (r > 240 and g > 240 and b > 240) or (r < 15 and g < 15 and b < 15):
                        continue
                    # Quantize to reduce noise (round to nearest 16)
                    qr = (r // 16) * 16
                    qg = (g // 16) * 16
                    qb = (b // 16) * 16
                    color_counts[(qr, qg, qb)] = color_counts.get((qr, qg, qb), 0) + 1

        doc.close()

        if not color_counts:
            return []

        # Return top 5 colors sorted by frequency
        sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        return [f"#{r:02X}{g:02X}{b:02X}" for (r, g, b), _ in sorted_colors]

    except Exception:
        logger.warning("Failed to extract colors from image", path=str(path), exc_info=True)
        return []


def list_font_files(fonts_dir: Path) -> list[dict[str, str]]:
    """List TTF/OTF font files and extract font family names.

    Returns a list of dicts with 'file' and 'family' keys.
    """
    fonts: list[dict[str, str]] = []
    if not fonts_dir.is_dir():
        return fonts

    for font_path in sorted(fonts_dir.iterdir()):
        if font_path.suffix.lower() in (".ttf", ".otf"):
            family = _read_font_family(font_path)
            fonts.append({
                "file": font_path.name,
                "family": family or font_path.stem,
            })

    return fonts


def _read_font_family(path: Path) -> str | None:
    """Read the font family name from a TTF/OTF file's name table."""
    try:
        with open(path, "rb") as f:
            # Read the offset table
            data = f.read(12)
            if len(data) < 12:
                return None
            _, num_tables = struct.unpack(">HH", data[:4])

            # Find the 'name' table
            name_offset = 0
            for _ in range(num_tables):
                entry = f.read(16)
                if len(entry) < 16:
                    return None
                tag = entry[:4]
                if tag == b"name":
                    _, name_offset, _ = struct.unpack(">III", entry[4:16])
                    break

            if name_offset == 0:
                return None

            # Read the name table
            f.seek(name_offset)
            header = f.read(6)
            if len(header) < 6:
                return None
            _, count, string_offset = struct.unpack(">HHH", header)

            # Search for name ID 1 (Font Family) with platform 3 (Windows) or 1 (Mac)
            for _ in range(count):
                record = f.read(12)
                if len(record) < 12:
                    return None
                platform_id, _, _, name_id, length, offset = struct.unpack(
                    ">HHHHHH", record
                )
                if name_id == 1:  # Font Family
                    current_pos = f.tell()
                    f.seek(name_offset + string_offset + offset)
                    name_data = f.read(length)
                    f.seek(current_pos)

                    if platform_id == 3:  # Windows — UTF-16 BE
                        try:
                            return name_data.decode("utf-16-be").strip()
                        except UnicodeDecodeError:
                            continue
                    elif platform_id == 1:  # Mac — ASCII/latin1
                        try:
                            return name_data.decode("latin-1").strip()
                        except UnicodeDecodeError:
                            continue

    except (OSError, struct.error):
        logger.debug("Could not read font family name", path=str(path))

    return None


def extract_pptx_theme(path: Path) -> dict[str, Any]:
    """Extract font and color info from a PPTX file's theme XML.

    Returns a dict with 'fonts' and 'colors' keys.
    """
    result: dict[str, Any] = {"fonts": [], "colors": []}

    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Look for theme XML
            theme_files = [n for n in zf.namelist() if n.startswith("ppt/theme/")]
            if not theme_files:
                return result

            for theme_file in theme_files:
                tree = ET.parse(zf.open(theme_file))
                root = tree.getroot()

                # Namespace handling for OOXML
                ns = {
                    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                }

                # Extract font scheme
                for font_scheme in root.iter(f"{{{ns['a']}}}fontScheme"):
                    for major in font_scheme.iter(f"{{{ns['a']}}}majorFont"):
                        for latin in major.iter(f"{{{ns['a']}}}latin"):
                            typeface = latin.get("typeface")
                            if typeface:
                                result["fonts"].append({"role": "heading", "typeface": typeface})
                    for minor in font_scheme.iter(f"{{{ns['a']}}}minorFont"):
                        for latin in minor.iter(f"{{{ns['a']}}}latin"):
                            typeface = latin.get("typeface")
                            if typeface:
                                result["fonts"].append({"role": "body", "typeface": typeface})

                # Extract theme colors
                for clr_scheme in root.iter(f"{{{ns['a']}}}clrScheme"):
                    for child in clr_scheme:
                        tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        for srgb in child.iter(f"{{{ns['a']}}}srgbClr"):
                            val = srgb.get("val")
                            if val:
                                result["colors"].append({
                                    "role": tag_name,
                                    "hex": f"#{val}",
                                })

    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        logger.warning("Failed to parse PPTX theme", path=str(path), exc_info=True)

    return result


def analyze_theme(theme_dir: Path) -> dict[str, Any]:
    """Analyze docs/theme/ and produce a theme configuration dict.

    Scans logos/, samples/, and fonts/ subdirectories. Gracefully degrades
    to defaults when assets are missing.
    """
    theme: dict[str, Any] = {
        "colors": dict(DEFAULT_THEME["colors"]),
        "fonts": dict(DEFAULT_THEME["fonts"]),
        "logos": [],
        "layouts": dict(DEFAULT_THEME["layouts"]),
        "_warnings": [],
    }

    logos_dir = theme_dir / "logos"
    samples_dir = theme_dir / "samples"
    fonts_dir = theme_dir / "fonts"

    # --- Logos and colors ---
    if logos_dir.is_dir():
        logo_files = sorted(
            p for p in logos_dir.iterdir()
            if p.suffix.lower() in (".png", ".svg", ".jpg", ".jpeg")
            and not p.name.startswith(".")
        )
        if logo_files:
            theme["logos"] = [f.name for f in logo_files]
            # Extract colors from the first PNG/JPG
            for logo in logo_files:
                if logo.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    colors = extract_colors_from_png(logo)
                    if colors:
                        theme["colors"]["primary"] = colors[0]
                        if len(colors) > 1:
                            theme["colors"]["secondary"] = colors[1]
                        if len(colors) > 2:
                            theme["colors"]["accent"] = colors[2]
                        break
        else:
            theme["_warnings"].append("No logo files found in docs/theme/logos/")
    else:
        theme["_warnings"].append("docs/theme/logos/ directory not found")

    # --- Fonts ---
    if fonts_dir.is_dir():
        font_list = list_font_files(fonts_dir)
        if font_list:
            theme["fonts"]["available"] = font_list
            # Use first font for heading, second (or first) for body
            theme["fonts"]["heading"] = font_list[0]["family"]
            if len(font_list) > 1:
                theme["fonts"]["body"] = font_list[1]["family"]
            else:
                theme["fonts"]["body"] = font_list[0]["family"]
        else:
            theme["_warnings"].append("No TTF/OTF files found in docs/theme/fonts/")
    else:
        theme["_warnings"].append("docs/theme/fonts/ directory not found")

    # --- Sample PPTX/PDF analysis ---
    if samples_dir.is_dir():
        sample_files = sorted(
            p for p in samples_dir.iterdir()
            if p.suffix.lower() in (".pptx", ".pdf")
            and not p.name.startswith(".")
        )
        if sample_files:
            for sample in sample_files:
                if sample.suffix.lower() == ".pptx":
                    pptx_theme = extract_pptx_theme(sample)
                    if pptx_theme["fonts"]:
                        theme["layouts"]["sample_fonts"] = pptx_theme["fonts"]
                        # Override heading/body from PPTX if not already set by TTF fonts
                        if "available" not in theme["fonts"]:
                            for ft in pptx_theme["fonts"]:
                                if ft["role"] == "heading":
                                    theme["fonts"]["heading"] = ft["typeface"]
                                elif ft["role"] == "body":
                                    theme["fonts"]["body"] = ft["typeface"]
                    if pptx_theme["colors"]:
                        theme["layouts"]["sample_colors"] = pptx_theme["colors"]
                    break  # Use the first sample
        else:
            theme["_warnings"].append("No PPTX/PDF files found in docs/theme/samples/")
    else:
        theme["_warnings"].append("docs/theme/samples/ directory not found")

    return theme


def write_theme_yaml(theme: dict[str, Any], output_path: Path) -> None:
    """Write the theme configuration to a YAML file.

    Warnings are written as comments, not as YAML data.
    """
    warnings = theme.pop("_warnings", [])

    yaml = YAML()
    yaml.default_flow_style = False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write("# Theme configuration — generated by docs:analyze (spec 002, FR-002).\n")
        f.write("# Edit freely; docs:auto and docs:update will respect your changes.\n")
        if warnings:
            f.write("#\n")
            f.write("# Warnings during inference:\n")
            for w in warnings:
                f.write(f"#   - {w}\n")
        f.write("\n")
        yaml.dump(theme, f)
