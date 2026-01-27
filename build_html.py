#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NOTEBOOKS = [
    ("polygon_ratio_geometry/polygon_ratio_problem.ipynb", "polygon_ratio_problem.html"),
    ("pysym/pysym_polygon_ratio_Wu_and_Groebner.ipynb", "pysym_polygon_ratio_Wu_and_Groebner.html"),
    ("newclid_methods/newclid_polygon_ratio.ipynb", "newclid_polygon_ratio.html"),
    ("aristotle/aristotle_polygon_ratio.ipynb", "aristotle_polygon_ratio.html"),
]
COMBINED_HTML = "polygon_ratio_all.html"
REQUIREMENTS_PATH = "requirements.txt"

BASE_FONT_SIZE_PT = 11
BODY_LINE_HEIGHT = 1.35
H1_EM = 1.6
H2_EM = 1.3
H3_EM = 1.15
H4_EM = 1.05
IFRAME_HEIGHT_PX = 1000


def _tag(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _rewrite_src(body_html: str, base_dir: Path, repo_root: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        src = match.group(1)
        if re.match(r"^(?:[a-z]+:)?//", src) or src.startswith("data:") or src.startswith("#"):
            return match.group(0)
        src_path = (base_dir / src).resolve()
        try:
            rel = src_path.relative_to(repo_root.resolve())
        except ValueError:
            return match.group(0)
        return f'src="{rel.as_posix()}"'

    return re.sub(r'src="([^"]+)"', repl, body_html)


def _add_heading_ids(body_html: str, prefix: str) -> tuple[str, list[tuple[int, str, str]]]:
    headings: list[tuple[int, str, str]] = []

    def strip_anchor(inner_html: str) -> str:
        return re.sub(
            r'<a[^>]*class="anchor-link"[^>]*>.*?</a>',
            "",
            inner_html,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()

    def strip_tags(inner_html: str) -> str:
        return re.sub(r"<[^>]+>", "", inner_html).strip()

    def repl(match: re.Match[str]) -> str:
        level = int(match.group(1))
        attrs = match.group(2) or ""
        inner_raw = match.group(3).strip()
        inner_clean = strip_anchor(inner_raw)
        display_text = strip_tags(inner_clean)
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", display_text).strip("-").lower()
        anchor = f"{prefix}-{slug}" if slug else f"{prefix}-h{level}-{len(headings)+1}"
        attrs = re.sub(r'\s+id="[^"]*"', "", attrs, flags=re.IGNORECASE)
        headings.append((level, display_text, anchor))
        return f"<h{level}{attrs} id=\"{anchor}\">{inner_clean}</h{level}>"

    body_html = re.sub(r"<h([1-4])([^>]*)>(.*?)</h\1>", repl, body_html, flags=re.DOTALL | re.IGNORECASE)
    return body_html, headings


def build_combined_html(html_paths: list[Path], output_path: Path, repo_root: Path) -> None:
    if not html_paths:
        raise ValueError("No HTML files provided for combination.")

    head_content = _tag(html_paths[0].read_text(encoding="utf-8", errors="ignore"), "head")

    sections: list[str] = []
    toc_items: list[str] = []
    part_break_inserted = False

    for idx, html_path in enumerate(html_paths):
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        body_content = _tag(html_text, "body")
        body_content = _rewrite_src(body_content, html_path.parent, repo_root)
        section_id = f"section-{html_path.stem}"
        body_content, headings = _add_heading_ids(body_content, section_id)
        title = headings[0][1] if headings else html_path.stem.replace("_", " ").title()

        toc_items.append(f'<li class="toc-section"><a href="#{section_id}">{title}</a>')
        if idx == 0:
            part_links = [
                f'<li class="toc-h{level}"><a href="#{anchor}">{text}</a></li>'
                for level, text, anchor in headings
                if re.search(r"\bpart\b", text, flags=re.IGNORECASE)
            ]
            if part_links:
                toc_items.append('<ul class="toc-sub">')
                toc_items.extend(part_links)
                toc_items.append("</ul>")
        toc_items.append("</li>")

        def add_back_link(match: re.Match[str]) -> str:
            nonlocal part_break_inserted
            level = int(match.group(1))
            attrs = match.group(2) or ""
            inner = match.group(3) or ""
            if not re.search(r"\bpart\b", inner, flags=re.IGNORECASE):
                return match.group(0)
            page_break = '<div class="page-break"></div>\n' if part_break_inserted else ""
            part_break_inserted = True
            return (
                page_break
                + '<div class="back-to-toc"><a href="#toc">Back to TOC</a></div>\n'
                + f"<h{level}{attrs}>{inner}</h{level}>"
            )

        body_content = re.sub(
            r"<h([1-4])([^>]*)>(.*?)</h\1>",
            add_back_link,
            body_content,
            flags=re.IGNORECASE | re.DOTALL,
        )

        sections.append(
            f'<section id="{section_id}" class="nb-section" data-source="{html_path.name}">\n'
            f"{body_content}\n</section>"
        )

    style = f"""<style>
body {{ font-size: {BASE_FONT_SIZE_PT}pt; line-height: {BODY_LINE_HEIGHT}; }}
.rendered_html {{ font-size: {BASE_FONT_SIZE_PT}pt; line-height: {BODY_LINE_HEIGHT}; }}
h1 {{ font-size: {H1_EM}em; }}
h2 {{ font-size: {H2_EM}em; }}
h3 {{ font-size: {H3_EM}em; }}
h4 {{ font-size: {H4_EM}em; }}
.rendered_html img, .rendered_html svg, .output_area img, .output_area svg, .output_area canvas {{
  max-width: 100% !important;
  height: auto !important;
  display: block;
  margin: 0.4em auto;
}}
.output_svg, .output_area, .output_subarea {{
  overflow: visible !important;
  max-height: none !important;
  width: 100% !important;
  height: auto !important;
}}
.output_scroll {{
  overflow: visible !important;
  max-height: none !important;
  height: auto !important;
}}
.output_svg svg, .output_area svg {{
  width: 100% !important;
  height: auto !important;
  max-height: none !important;
}}
.rendered_html iframe, .output_area iframe {{
  width: 100% !important;
  height: {IFRAME_HEIGHT_PX}px !important;
}}
@media print {{
  body {{ font-size: {BASE_FONT_SIZE_PT}pt; line-height: {BODY_LINE_HEIGHT}; }}
  .rendered_html {{ font-size: {BASE_FONT_SIZE_PT}pt; line-height: {BODY_LINE_HEIGHT}; }}
  h1 {{ font-size: {H1_EM}em; }}
  h2 {{ font-size: {H2_EM}em; }}
  h3 {{ font-size: {H3_EM}em; }}
  h4 {{ font-size: {H4_EM}em; }}
  .rendered_html img, .rendered_html svg, .output_area img, .output_area svg, .output_area canvas {{
    max-width: 100% !important;
    height: auto !important;
    display: block;
    margin: 0.4em auto;
  }}
  .output_svg, .output_area, .output_subarea {{
    overflow: visible !important;
    max-height: none !important;
    width: 100% !important;
    height: auto !important;
  }}
  .output_scroll {{
    overflow: visible !important;
    max-height: none !important;
    height: auto !important;
  }}
  .output_svg svg, .output_area svg {{
    width: 100% !important;
    height: auto !important;
    max-height: none !important;
  }}
  .rendered_html iframe, .output_area iframe {{
    width: 100% !important;
    height: {IFRAME_HEIGHT_PX}px !important;
  }}
}}
.page-break {{ page-break-after: always; }}
.nb-section {{ page-break-inside: auto; }}
.toc {{ max-width: 900px; margin: 20px auto 40px; padding: 16px 20px; border: 1px solid #ddd; border-radius: 8px; }}
.toc h2 {{ margin: 0 0 10px; font-size: 20px; }}
.toc ul {{ margin: 0; padding-left: 18px; list-style: none; }}
.toc-sub {{ margin: 6px 0 10px; padding-left: 14px; }}
.toc a {{ text-decoration: none; }}
.toc-section {{ margin-top: 6px; font-weight: 600; }}
.toc-h2, .toc-h3, .toc-h4 {{ margin: 4px 0; font-weight: 400; }}
.back-to-toc {{ margin: 8px 0 6px; font-size: 0.9em; }}
.back-to-toc a {{ text-decoration: none; }}
</style>"""

    combined = "\n".join(
        [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            head_content,
            style,
            "</head>",
            "<body>",
            '<nav id="toc" class="toc">',
            "<h2>Table of Contents</h2>",
            "<ul>",
            "\n".join(toc_items),
            "</ul>",
            "</nav>",
            "\n".join(sections),
            "</body>",
            "</html>",
        ]
    )

    output_path.write_text(combined, encoding="utf-8")


def write_requirements_from_venv(requirements_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--not-required", "--format=freeze"],
        check=True,
        capture_output=True,
        text=True,
    )
    content = result.stdout.strip()
    if not content:
        raise RuntimeError("pip list returned empty output; cannot write requirements.txt")
    requirements_path.write_text(content + "\n", encoding="utf-8")


def _convert_notebook(repo_root: Path, nb_rel: str, html_name: str) -> Path:
    nb_path = repo_root / nb_rel
    if not nb_path.exists():
        raise FileNotFoundError(f"Missing notebook: {nb_path}")
    output_dir = nb_path.parent
    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "nbconvert",
        "--to",
        "html",
        "--output",
        html_name,
        "--output-dir",
        str(output_dir),
        str(nb_path),
    ]
    print(f"Generating: {output_dir / html_name}")
    subprocess.run(cmd, check=True)
    return output_dir / html_name


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    write_requirements_from_venv(repo_root / REQUIREMENTS_PATH)

    max_workers = min(4, max(1, os.cpu_count() or 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_convert_notebook, repo_root, nb_rel, html_name)
            for nb_rel, html_name in NOTEBOOKS
        ]
        html_paths = [future.result() for future in futures]

    build_combined_html(html_paths, repo_root / COMBINED_HTML, repo_root)
    print(f"Combined HTML: {repo_root / COMBINED_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
