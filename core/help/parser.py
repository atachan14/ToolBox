from __future__ import annotations

import re
from pathlib import Path

from .models import HelpDocument, HelpImage, HelpSection


HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _slugify(text: str) -> str:
    value = re.sub(r"[^\w\s-]", "", text.strip().lower())
    value = re.sub(r"[-\s]+", "-", value).strip("-")
    return value or "section"


def _make_unique_id(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def _is_image_target(target: str) -> bool:
    cleaned = target.split("#", 1)[0].split("?", 1)[0].strip()
    return Path(cleaned).suffix.lower() in IMAGE_SUFFIXES


def _normalize_body(markdown: str) -> str:
    def replace_image(match: re.Match[str]) -> str:
        alt = (match.group(1) or "").strip() or Path(match.group(2)).name
        return f"[{alt}]({match.group(2)})"

    return IMAGE_LINK_RE.sub(replace_image, markdown).strip()


def _collect_image_paths(markdown: str, base_dir: Path) -> list[Path]:
    ordered: list[Path] = []
    seen: set[Path] = set()

    def add_target(target: str):
        if not _is_image_target(target):
            return
        path = (base_dir / target).resolve()
        if path in seen:
            return
        seen.add(path)
        ordered.append(path)

    for alt, target in IMAGE_LINK_RE.findall(markdown):
        add_target(target)
    for label, target in MARKDOWN_LINK_RE.findall(markdown):
        add_target(target)
    return ordered


def parse_help_document(markdown_path: Path) -> HelpDocument:
    text = markdown_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    used_ids: set[str] = set()
    sections: list[HelpSection] = []
    current_title = markdown_path.stem
    current_level = 1
    current_id = _make_unique_id("document", used_ids)
    body_lines: list[str] = []

    def flush_current():
        nonlocal body_lines
        sections.append(
            HelpSection(
                id=current_id,
                title=current_title,
                level=current_level,
                body_markdown=_normalize_body("\n".join(body_lines)),
                image_paths=_collect_image_paths("\n".join(body_lines), markdown_path.parent),
            )
        )
        body_lines = []

    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            if body_lines or sections:
                flush_current()
            current_level = len(match.group(1))
            current_title = match.group(2).strip()
            current_id = _make_unique_id(_slugify(current_title), used_ids)
            continue
        body_lines.append(line)

    flush_current()

    stack: list[HelpSection] = []
    for section in sections:
        while stack and stack[-1].level >= section.level:
            stack.pop()
        if stack:
            section.parent_id = stack[-1].id
            stack[-1].children.append(section.id)
        stack.append(section)

    images: list[HelpImage] = []
    seen_image_paths: set[Path] = set()
    for section in sections:
        for path in section.image_paths:
            if path in seen_image_paths:
                continue
            seen_image_paths.add(path)
            images.append(HelpImage(path=path, label=path.name))

    title = sections[0].title if sections else markdown_path.stem
    return HelpDocument(title=title, markdown_path=markdown_path, sections=sections, images=images)
