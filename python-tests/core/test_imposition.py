import pytest

from epub_a4_word.imposition import build_imposition


def test_signature16_orders_first_signature_for_cut_fold_and_nesting() -> None:
    plan = build_imposition(16, "signature16")

    assert plan.sides == (
        (16, 1, 14, 3),
        (2, 15, 4, 13),
        (12, 5, 10, 7),
        (6, 11, 8, 9),
    )
    assert plan.signature_count == 1
    assert plan.paper_sheet_count == 2
    assert plan.padded_page_count == 16


def test_signature16_pads_only_the_end_of_the_last_signature() -> None:
    plan = build_imposition(233, "signature16")

    assert len(plan.sides) == 60
    assert plan.signature_count == 15
    assert plan.paper_sheet_count == 30
    assert plan.padded_page_count == 240
    assert plan.sides[-4:] == (
        (None, 225, None, 227),
        (226, None, 228, None),
        (None, 229, None, 231),
        (230, None, 232, 233),
    )


def test_four_up_keeps_normal_reading_order() -> None:
    plan = build_imposition(5, "four_up")

    assert plan.sides == ((1, 2, 3, 4), (5, None, None, None))
    assert plan.paper_sheet_count == 2
    assert plan.signature_count == 0


def test_single_a5_maps_each_content_page_to_one_sheet() -> None:
    plan = build_imposition(3, "single_a5")

    assert plan.sides == ((1,), (2,), (3,))
    assert plan.paper_sheet_count == 3
    assert plan.signature_count == 0
    assert plan.padded_page_count == 3


def test_single_4x6_maps_each_content_page_to_one_sheet() -> None:
    plan = build_imposition(2, "single_4x6")

    assert plan.sides == ((1,), (2,))
    assert plan.paper_sheet_count == 2
    assert plan.signature_count == 0
    assert plan.padded_page_count == 2


def test_right_binding_mirrors_each_signature_row_without_reordering_pages() -> None:
    plan = build_imposition(16, "signature16", "right")

    assert plan.sides == (
        (1, 16, 3, 14),
        (15, 2, 13, 4),
        (5, 12, 7, 10),
        (11, 6, 9, 8),
    )
    assert sorted(page for side in plan.sides for page in side if page) == list(
        range(1, 17)
    )


def test_right_binding_mirrors_four_up_rows() -> None:
    assert build_imposition(4, "four_up", "right").sides == ((2, 1, 4, 3),)


@pytest.mark.parametrize("mode", ["single_a5", "single_4x6", "b6_on_a5"])
def test_single_page_modes_keep_logical_order_for_right_binding(mode: str) -> None:
    assert build_imposition(3, mode, "right").sides == ((1,), (2,), (3,))


def test_imposition_rejects_unknown_binding_direction() -> None:
    with pytest.raises(ValueError, match="binding direction"):
        build_imposition(4, "four_up", "middle")
