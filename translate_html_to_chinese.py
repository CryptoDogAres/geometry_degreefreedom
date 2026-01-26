#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from deep_translator import GoogleTranslator


SKIP_TAGS = {
    "script",
    "style",
    "code",
    "pre",
    "math",
    "svg",
    "noscript",
}


def should_skip(node: NavigableString) -> bool:
    parent = node.parent
    if not parent:
        return True
    if parent.name in SKIP_TAGS:
        return True
    parent_class = parent.get("class") or []
    if any("math" in c.lower() for c in parent_class):
        return True
    if parent.name in {"annotation", "semantics", "mjx-container"}:
        return True
    return False


def chunk_text(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start + 200:
                end = space
        parts.append(text[start:end])
        start = end
    return parts


def translate_text(text: str, translator: GoogleTranslator) -> str:
    chunks = chunk_text(text)
    translated_chunks: list[str] = []
    for chunk in chunks:
        try:
            result = translator.translate(chunk)
        except Exception:
            result = None
        if result is None:
            # Keep original chunk if translation failed.
            result = chunk
        translated_chunks.append(result)
    return "".join(translated_chunks)


def translate_html_file(path: Path, translator: GoogleTranslator) -> Path:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    cache: dict[str, str] = {}

    for node in soup.find_all(string=True):
        if not isinstance(node, NavigableString):
            continue
        raw = str(node)
        if raw.strip() == "":
            continue
        if should_skip(node):
            continue

        lead = re.match(r"^\s*", raw).group(0)
        trail = re.search(r"\s*$", raw).group(0)
        core = raw.strip()

        if core in cache:
            translated = cache[core]
        else:
            translated = translate_text(core, translator)
            cache[core] = translated

        node.replace_with(f"{lead}{translated}{trail}")

    out_path = path.with_name(f"{path.stem}_chinese{path.suffix}")
    out_path.write_text(str(soup), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate HTML files to Simplified Chinese.")
    parser.add_argument("--root", default=".", help="Root directory to search for HTML files.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    translator = GoogleTranslator(source="auto", target="zh-CN")

    html_files = [
        p
        for p in root.rglob("*.html")
        if not p.name.endswith("_chinese.html")
    ]

    if not html_files:
        print("No HTML files found.")
        return 0

    for html_path in html_files:
        translate_html_file(html_path, translator)
        print(f"Translated: {html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
