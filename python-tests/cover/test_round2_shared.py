from __future__ import annotations

from pathlib import Path

from epub_a4_word.cover.models import ElementKind
from epub_a4_word.cover.project_io import loads_project
from epub_a4_word.cover.search.google_books import GoogleBooksProvider
from epub_a4_word.cover.search.models import CoverSearchRequest, SearchKind
from epub_a4_word.cover.search.open_library import OpenLibraryProvider
from epub_a4_word.cover.service import inspect_source, new_project
from epub_a4_word.cover.templates import apply_template
from epub_a4_word.models import TextBlock, TextRun
from epub_a4_word.pagination import LayoutSettings, paginate


class CaptureHttp:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = []

    def get_json(
        self,
        url: str,
        params: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        self.calls.append((url, dict(params), None if headers is None else dict(headers)))
        return self.payload


def test_b6_pagination_reserves_enough_word_rendering_headroom() -> None:
    block = TextBlock((TextRun("字" * 1700),), style="body")
    pages = paginate([block], LayoutSettings(imposition_mode="b6_on_a5"), {})

    assert len(pages) == 2


def test_inspect_source_returns_automatic_epub_page_count(fixtures_dir: Path) -> None:
    result = inspect_source(str(fixtures_dir / "cover/metadata.epub"), 128.0, 182.0)

    assert int(result["page_count"]) >= 1
    assert result["page_count_estimated"] is True


def test_default_minimal_template_keeps_source_cover_without_generated_text(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    import json

    settings = {
        "working_dir": str(tmp_path / "work"),
        "trim_width_mm": 148.0,
        "trim_height_mm": 210.0,
        "page_count": 160,
        "paper_caliper_mm": 0.09,
        "bleed_mm": 0.0,
        "overlap_mm": 5.0,
    }
    project = loads_project(
        new_project(str(fixtures_dir / "cover/metadata.epub"), json.dumps(settings))
    )
    result = apply_template(project, "minimal")

    assert "source-cover-image" in result.elements_by_id
    assert not any(
        element.kind in {ElementKind.TEXT, ElementKind.BARCODE_PLACEHOLDER}
        for element in result.elements
    )


def test_google_books_request_includes_configured_api_key() -> None:
    http = CaptureHttp({"items": []})
    provider = GoogleBooksProvider(http, api_key="BOOKS_API_KEY")

    provider.search(CoverSearchRequest(kind=SearchKind.FRONT, title="測試書"))

    _url, params, _headers = http.calls[0]
    assert params["key"] == "BOOKS_API_KEY"


def test_open_library_request_identifies_application() -> None:
    http = CaptureHttp({"docs": []})
    provider = OpenLibraryProvider(http)

    provider.search(CoverSearchRequest(kind=SearchKind.FRONT, title="測試書"))

    _url, _params, headers = http.calls[0]
    assert headers is not None
    assert "EPUB2A4-CoverTool" in headers["User-Agent"]
    assert "github.com/eightkingdomsalliedforces-hash/epub2a4" in headers["User-Agent"]


def test_open_library_accepts_current_unprefixed_work_key() -> None:
    http = CaptureHttp(
        {
            "docs": [
                {
                    "key": "OL24577320W",
                    "title": "A Certain Magical Index, Vol. 1 - light novel",
                    "author_name": ["鎌池和馬"],
                    "isbn": ["9780316339124"],
                    "cover_i": 123456,
                    "edition_key": ["OL32593075M"],
                }
            ]
        }
    )
    provider = OpenLibraryProvider(http, min_interval_seconds=0)

    response = provider.search(
        CoverSearchRequest(
            kind=SearchKind.FRONT,
            title="A Certain Magical Index",
        )
    )

    assert len(response.candidates) == 1
    assert response.candidates[0].source_page == (
        "https://openlibrary.org/works/OL24577320W"
    )
