from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QRectF

from epub_a4_word_desktop.cover.crop_dialog import CropDialog


def _source_png(tmp_path: Path) -> Path:
    path = tmp_path / "source.png"
    Image.new("RGB", (200, 100), "white").save(path)
    return path


def test_crop_rect_is_normalized(qtbot, tmp_path: Path) -> None:
    dialog = CropDialog(_source_png(tmp_path), QRectF(0.1, 0.2, 0.7, 0.6))
    qtbot.addWidget(dialog)
    result = dialog.crop_rect()
    assert result.x() == pytest.approx(0.1)
    assert result.y() == pytest.approx(0.2)
    assert result.width() == pytest.approx(0.7)
    assert result.height() == pytest.approx(0.6)
    assert 0 <= result.x() <= 1
    assert 0 <= result.y() <= 1
    assert result.right() <= 1
    assert result.bottom() <= 1


def test_crop_margins_match_normalized_rectangle(qtbot, tmp_path: Path) -> None:
    dialog = CropDialog(_source_png(tmp_path), QRectF(0.1, 0.2, 0.7, 0.6))
    qtbot.addWidget(dialog)
    assert dialog.crop_margins() == pytest.approx(
        {
            "crop_left": 0.1,
            "crop_top": 0.2,
            "crop_right": 0.2,
            "crop_bottom": 0.2,
        }
    )


def test_crop_rectangle_must_leave_positive_area(qtbot, tmp_path: Path) -> None:
    dialog = CropDialog(_source_png(tmp_path))
    qtbot.addWidget(dialog)
    with pytest.raises(ValueError, match="裁切"):
        dialog.set_crop_rect(QRectF(0.5, 0.5, 0.0, 0.5))
