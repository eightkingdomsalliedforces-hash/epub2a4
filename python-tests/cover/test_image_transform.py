from __future__ import annotations

from PIL import Image

from epub_a4_word.cover.render import transform_image_to_box


def test_contain_preserves_aspect_ratio_and_centers() -> None:
    source = Image.new("RGBA", (200, 100), "red")
    result = transform_image_to_box(source, (100, 100), fit="contain")

    assert result.getpixel((50, 10))[3] == 0
    assert result.getpixel((50, 50))[:3] == (255, 0, 0)
    assert result.getpixel((50, 90))[3] == 0


def test_scale_and_offset_use_same_normalized_box_coordinates() -> None:
    source = Image.new("RGBA", (100, 100), "blue")
    result = transform_image_to_box(
        source,
        (100, 100),
        fit="contain",
        scale=0.5,
        offset_x=0.25,
        offset_y=-0.25,
    )

    assert result.getpixel((25, 75))[3] == 0
    assert result.getpixel((75, 25))[:3] == (0, 0, 255)


def test_cover_fills_box_and_original_keeps_source_ratio() -> None:
    source = Image.new("RGBA", (200, 100), "green")
    cover = transform_image_to_box(source, (100, 100), fit="cover")
    original = transform_image_to_box(source, (100, 100), fit="original")

    assert cover.getbbox() == (0, 0, 100, 100)
    assert original.getpixel((50, 10))[3] == 0
    assert original.getpixel((50, 50))[:3] == (0, 128, 0)


def test_crop_is_applied_before_fit() -> None:
    source = Image.new("RGBA", (100, 50), "red")
    for x in range(50, 100):
        for y in range(50):
            source.putpixel((x, y), (0, 0, 255, 255))

    result = transform_image_to_box(
        source,
        (50, 50),
        fit="cover",
        crop={"left": 0.5, "top": 0.0, "right": 1.0, "bottom": 1.0},
    )
    assert result.getpixel((25, 25))[:3] == (0, 0, 255)
