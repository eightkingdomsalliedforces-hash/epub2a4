from __future__ import annotations

from epub_a4_word.cover.publisher_directory import publisher_profile
from epub_a4_word.cover.search.logo_models import LogoSourceCategory
from epub_a4_word.cover.search.publisher_logo import PublisherLogoSearch


class FakeJsonClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, url: str, params: dict[str, object], headers=None):
        self.calls.append((url, dict(params)))
        if "commons.wikimedia.org" in url:
            return {
                "continue": {"gsroffset": 20, "continue": "gsroffset||"},
                "query": {
                    "pages": [
                        {
                            "pageid": 123,
                            "title": "File:Kadokawa logo.svg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/logo.svg",
                                    "thumburl": "https://upload.wikimedia.org/logo-thumb.png",
                                    "width": 1024,
                                    "height": 280,
                                    "mime": "image/svg+xml",
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        "Artist": {"value": "Example"},
                                    },
                                }
                            ],
                        }
                    ]
                },
            }
        return {"query": {"pages": []}}


def test_wikimedia_results_are_normalized_and_page_token_is_returned() -> None:
    search = PublisherLogoSearch(http=FakeJsonClient())

    page = search.search("台灣角川", profile=publisher_profile("台灣角川"), limit=20)

    candidate = page.candidates[0]
    assert candidate.source_category is LogoSourceCategory.WIKIMEDIA
    assert candidate.image_url == "https://upload.wikimedia.org/logo.svg"
    assert candidate.preview_url.endswith("logo-thumb.png")
    assert candidate.media_type == "image/svg+xml"
    assert candidate.license_text == "CC BY-SA 4.0"
    assert page.next_page_token
    assert len(page.candidates) <= 20


def test_search_uses_next_page_token_for_another_page() -> None:
    client = FakeJsonClient()
    search = PublisherLogoSearch(http=client)
    first = search.search("台灣角川", profile=publisher_profile("台灣角川"), limit=20)

    search.search(
        "台灣角川",
        profile=publisher_profile("台灣角川"),
        page_token=first.next_page_token,
        limit=20,
    )

    commons_calls = [params for url, params in client.calls if "commons.wikimedia.org" in url]
    assert commons_calls[-1]["gsroffset"] == 20
