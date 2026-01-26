#!/usr/bin/env python3
"""
Run:
  python build_html.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


NOTEBOOKS = [
    ("polygon_ratio_geometry/polygon_ratio_problem.ipynb", "polygon_ratio_problem.html"),
    ("pysym/pysym_polygon_ratio_Wu_and_Groebner.ipynb", "pysym_polygon_ratio_Wu_and_Groebner.html"),
    ("newclid_methods/newclid_polygon_ratio.ipynb", "newclid_polygon_ratio.html"),
]
COMBINED_HTML = "polygon_ratio_all.html"
REQUIREMENTS_PATH = "requirements.txt"


def _extract_tag_content(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _rewrite_asset_paths(body_html: str, base_dir: Path, repo_root: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        src = match.group(1)
        if re.match(r"^(?:[a-z]+:)?//", src) or src.startswith("data:") or src.startswith("#"):
            return match.group(0)

        src_path = (base_dir / src).resolve()
        try:
            rel = src_path.relative_to(repo_root.resolve())
        except ValueError:
            # If it points outside repo_root, keep as-is.
            return match.group(0)

        rel_posix = rel.as_posix()
        return f'src="{rel_posix}"'

    return re.sub(r'src="([^"]+)"', repl, body_html)


def _inject_back_button(html_text: str, href: str) -> str:
    css = """
<style>
.back-to-index {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 9999;
  padding: 10px 14px;
  background: #111;
  color: #fff;
  text-decoration: none;
  border-radius: 999px;
  box-shadow: 0 6px 16px rgba(0,0,0,0.25);
  font-family: Arial, sans-serif;
  font-size: 14px;
}
.back-to-index:hover { background: #333; }
</style>
""".strip()

    button = f'<a class="back-to-index" href="{href}">Back to index</a>'

    if "</head>" in html_text:
        html_text = html_text.replace("</head>", f"{css}\n</head>", 1)
    else:
        html_text = css + "\n" + html_text

    if "<body" in html_text:
        html_text = re.sub(r"(<body[^>]*>)", r"\\1\n" + button, html_text, count=1)
    else:
        html_text += "\n" + button

    return html_text


def _apply_back_button(html_path: Path, repo_root: Path) -> None:
    index_path = (repo_root / "index.html").resolve()
    rel = os.path.relpath(index_path, html_path.parent).replace("\\", "/")
    html_text = html_path.read_text(encoding="utf-8", errors="ignore")
    html_text = _inject_back_button(html_text, rel)
    html_path.write_text(html_text, encoding="utf-8")


def build_combined_html(html_paths: list[Path], output_path: Path, repo_root: Path) -> None:
    if not html_paths:
        raise ValueError("No HTML files provided for combination.")

    first_html = html_paths[0].read_text(encoding="utf-8", errors="ignore")
    head_content = _extract_tag_content(first_html, "head")

    sections: list[str] = []
    for idx, html_path in enumerate(html_paths):
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        body_content = _extract_tag_content(html_text, "body")
        body_content = _rewrite_asset_paths(body_content, html_path.parent, repo_root)
        section = f'<section class="nb-section" data-source="{html_path.name}">\n{body_content}\n</section>'
        sections.append(section)
        if idx < len(html_paths) - 1:
            sections.append('<div class="page-break"></div>')

    combined = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        head_content,
        "<style>",
        ".page-break { page-break-after: always; }",
        ".nb-section { page-break-after: always; }",
        "</style>",
        "</head>",
        "<body>",
        "\n".join(sections),
        "</body>",
        "</html>",
    ]

    output_path.write_text("\n".join(combined), encoding="utf-8")


def write_requirements_from_venv(requirements_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "list",
            "--not-required",
            "--format=freeze",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    content = result.stdout.strip()
    if not content:
        raise RuntimeError("pip list returned empty output; cannot write requirements.txt")
    requirements_path.write_text(content + "\n", encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    requirements_file = repo_root / REQUIREMENTS_PATH
    write_requirements_from_venv(requirements_file)
    html_paths: list[Path] = []
    for nb_rel, html_name in NOTEBOOKS:
        nb_path = repo_root / nb_rel
        if not nb_path.exists():
            print(f"Missing notebook: {nb_path}", file=sys.stderr)
            return 1

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
        html_path = output_dir / html_name
        _apply_back_button(html_path, repo_root)
        html_paths.append(html_path)

    combined_html_path = repo_root / COMBINED_HTML
    build_combined_html(html_paths, combined_html_path, repo_root)
    _apply_back_button(combined_html_path, repo_root)
    print(f"Combined HTML: {combined_html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
