from __future__ import annotations

from epub_a4_word.cover.isbn import (
    canonical_isbn13,
    encode_ean13_modules,
    isbn13_from_isbn10,
    normalize_isbn,
    preferred_isbn,
    valid_isbns,
)
from epub_a4_word.cover.search.google_books import GoogleBooksProvider
from epub_a4_word.cover.search.models import CoverSearchRequest


class FakeHttp:
    def get_json(self, _url, _params):
        return {
            "items": [
                {
                    "id": "book-1",
                    "volumeInfo": {
                        "title": "Example Volume 1",
                        "authors": ["Author"],
                        "industryIdentifiers": [
                            {"type": "ISBN_10", "identifier": "0-306-40615-2"},
                            {"type": "ISBN_13", "identifier": "978-0-306-40615-7"},
                            {"type": "OTHER", "identifier": "550e8400-e29b-41d4-a716-446655440000"},
                        ],
                        "imageLinks": {"thumbnail": "https://books.google.test/cover.jpg"},
                        "infoLink": "https://books.google.test/book/1",
                    },
                }
            ]
        }


class Isbn10OnlyHttp:
    def get_json(self, _url, _params):
        return {
            "items": [
                {
                    "id": "book-10",
                    "volumeInfo": {
                        "title": "ISBN-10 only",
                        "industryIdentifiers": [
                            {"type": "ISBN_10", "identifier": "0-306-40615-2"},
                        ],
                        "imageLinks": {"thumbnail": "https://books.google.test/cover-10.jpg"},
                        "infoLink": "https://books.google.test/book/10",
                    },
                }
            ]
        }


def test_normalize_isbn_accepts_valid_isbn10_and_isbn13() -> None:
    assert normalize_isbn("0-306-40615-2") == "0306406152"
    assert normalize_isbn("978-0-306-40615-7") == "9780306406157"


def test_normalize_isbn_rejects_uuid_and_bad_checksum() -> None:
    assert normalize_isbn("550e8400-e29b-41d4-a716-446655440000") == ""
    assert normalize_isbn("9780306406158") == ""
    assert normalize_isbn("0306406153") == ""


def test_valid_isbns_deduplicates_and_prefers_isbn13() -> None:
    values = valid_isbns(
        ["0-306-40615-2", "978-0-306-40615-7", "9780306406157", "not-an-isbn"]
    )
    assert values == ("0306406152", "9780306406157")
    assert preferred_isbn(values) == "9780306406157"


def test_isbn10_converts_to_canonical_ean13() -> None:
    assert isbn13_from_isbn10("0-306-40615-2") == "9780306406157"
    assert canonical_isbn13("0306406152") == "9780306406157"
    assert canonical_isbn13("9780306406157") == "9780306406157"
    assert canonical_isbn13("not-an-isbn") == ""
    assert preferred_isbn(("0306406152",)) == "9780306406157"


def test_ean13_module_pattern_has_standard_guards_and_length() -> None:
    modules = encode_ean13_modules("9780306406157")
    assert len(modules) == 95
    assert modules[:3] == "101"
    assert modules[45:50] == "01010"
    assert modules[-3:] == "101"


def test_google_books_candidate_keeps_isbn10_and_isbn13() -> None:
    provider = GoogleBooksProvider(FakeHttp(), api_key="test")
    response = provider.search(CoverSearchRequest(title="Example Volume 1"))
    candidate = response.candidates[0]
    assert candidate.isbns == ("0306406152", "9780306406157")
    assert candidate.isbn == "9780306406157"


def test_google_books_isbn10_only_candidate_uses_convertible_isbn13() -> None:
    provider = GoogleBooksProvider(Isbn10OnlyHttp(), api_key="test")
    response = provider.search(CoverSearchRequest(title="ISBN-10 only"))
    candidate = response.candidates[0]
    assert candidate.isbns == ("0306406152",)
    assert candidate.isbn == "9780306406157"
