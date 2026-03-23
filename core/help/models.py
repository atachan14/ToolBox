from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HelpImage:
    path: Path
    label: str


@dataclass
class HelpSection:
    id: str
    title: str
    level: int
    body_markdown: str
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)
    image_paths: list[Path] = field(default_factory=list)


@dataclass
class HelpDocument:
    title: str
    markdown_path: Path
    sections: list[HelpSection]
    images: list[HelpImage]
