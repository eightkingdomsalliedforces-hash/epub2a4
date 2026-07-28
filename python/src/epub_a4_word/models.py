from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias


WritingMode = Literal["taiwan_vertical", "horizontal"]
BindingDirection = Literal["right", "left"]


@dataclass(frozen=True)
class TextRun:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True)
class TextBlock:
    runs: tuple[TextRun, ...]
    style: str = "body"
    page_break_before: bool = False

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass(frozen=True)
class ImageBlock:
    resource_path: str
    alt_text: str = ""
    page_break_before: bool = False


@dataclass(frozen=True)
class PageBreakBlock:
    pass


ContentBlock: TypeAlias = TextBlock | ImageBlock | PageBreakBlock


@dataclass
class ParsedBook:
    source_path: Path
    title: str = ""
    author: str = ""
    language: str = ""
    blocks: list[ContentBlock] = field(default_factory=list)
    resources: dict[str, bytes] = field(default_factory=dict)
    media_types: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
