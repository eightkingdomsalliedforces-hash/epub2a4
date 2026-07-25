"""Desktop application package for EPUB/Word layout and cover editing."""

from __future__ import annotations

from epub_a4_word.cover import templates as _cover_templates


# The approved desktop labels used these IDs before the shared core finalized its
# public template identifiers. Register one-release aliases in the desktop
# package so legacy project/UI values delegate to the canonical core builders.
_TEMPLATE_ID_ALIASES = {
    "minimal": "minimal_text",
    "full_bleed_image": "full_spread",
    "classic_book": "front_image_plain_back",
}
for _alias, _canonical in _TEMPLATE_ID_ALIASES.items():
    _cover_templates._BUILDERS.setdefault(  # type: ignore[attr-defined]
        _alias,
        _cover_templates._BUILDERS[_canonical],  # type: ignore[attr-defined]
    )


__all__: tuple[str, ...] = ()
