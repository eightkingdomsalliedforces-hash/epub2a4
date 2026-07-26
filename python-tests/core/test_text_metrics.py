from epub_a4_word.text_metrics import paragraph_metrics, word_safety_points


def test_fixed_line_height_is_rounded_up_to_half_point() -> None:
    metrics = paragraph_metrics(8.5, 1.23, 2.5)
    assert metrics.line_height_pt == 11.5
    assert metrics.spacing_after_pt == 2.5


def test_fixed_line_height_never_uses_less_than_130_percent() -> None:
    assert paragraph_metrics(10.0, 1.0, 0.0).line_height_pt == 13.0


def test_all_modes_have_word_bottom_safety() -> None:
    assert word_safety_points("single_a5", 0.0) == 28.0
    assert word_safety_points("single_4x6", 0.0) == 28.0
    assert word_safety_points("four_up", 0.0) == 24.0
    assert word_safety_points("signature16", 0.0) == 24.0
    assert word_safety_points("b6_on_a5", 0.0) == 42.0
