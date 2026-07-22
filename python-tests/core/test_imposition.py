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
