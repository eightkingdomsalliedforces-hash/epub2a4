from __future__ import annotations

from epub_a4_word.cover.search.gutendex import GutendexProvider
from epub_a4_word.cover.search.models import CoverSearchRequest, SearchKind


class FakeHttp:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.calls = []

    def get_json(self, url, params, headers=None):
        self.calls.append((url, dict(params), headers))
        return self.payload


def test_maps_jpeg_cover_to_project_gutenberg_candidate() -> None:
    http = FakeHttp(
        {
            "results": [
                {
                    "id": 1342,
                    "title": "Pride and Prejudice",
                    "authors": [{"name": "Austen, Jane"}],
                    "languages": ["en"],
                    "formats": {
                        "image/jpeg": "https://www.gutenberg.org/cache/epub/1342/pg1342.cover.medium.jpg"
                    },
                }
            ]
        }
    )

    response = GutendexProvider(http).search(
        CoverSearchRequest(
            kind=SearchKind.FRONT,
            title="Pride and Prejudice",
            author="Jane Austen",
            locale="en",
        )
    )

    assert len(response.candidates) == 1
    candidate = response.candidates[0]
    assert candidate.provider == "gutendex"
    assert candidate.candidate_id == "1342"
    assert candidate.title == "Pride and Prejudice"
    assert candidate.author == "Austen, Jane"
    assert candidate.image_url.endswith("pg1342.cover.medium.jpg")
    assert candidate.source_page == "https://www.gutenberg.org/ebooks/1342"
    assert http.calls[0][0] == "https://gutendex.com/books"
    assert http.calls[0][1]["search"] == "Pride and Prejudice Jane Austen"
    assert http.calls[0][1]["languages"] == "en"


def test_ignores_records_without_cover_images_and_upgrades_http_image_url() -> None:
    http = FakeHttp(
        {
            "results": [
                {"id": 1, "title": "No Cover", "authors": [], "formats": {}},
                {
                    "id": 2,
                    "title": "Cover",
                    "authors": [],
                    "formats": {"image/jpeg": "http://www.gutenberg.org/cover.jpg"},
                },
            ]
        }
    )

    response = GutendexProvider(http).search(
        CoverSearchRequest(kind=SearchKind.FRONT, title="Cover")
    )

    assert [candidate.candidate_id for candidate in response.candidates] == ["2"]
    assert response.candidates[0].image_url == "https://www.gutenberg.org/cover.jpg"


def test_non_front_search_does_not_call_gutendex() -> None:
    http = FakeHttp({"results": []})

    response = GutendexProvider(http).search(
        CoverSearchRequest(kind=SearchKind.BACK, title="Pride and Prejudice")
    )

    assert response.candidates == ()
    assert http.calls == []
