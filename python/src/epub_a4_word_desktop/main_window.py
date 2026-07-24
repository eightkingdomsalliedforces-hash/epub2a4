from __future__ import annotations

from enum import StrEnum
from typing import Any

from PySide6.QtWidgets import QMainWindow, QStackedWidget

from .pages import CoverPage, ConverterPage, HomePage


class AppRoute(StrEnum):
    HOME = "home"
    CONVERTER = "converter"
    COVER = "cover"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("EPUB／Word 排版與封面工具")
        self.resize(1280, 820)

        self.stack = QStackedWidget(self)
        self.stack.setObjectName("main-page-stack")
        self.setCentralWidget(self.stack)

        self.home_page = HomePage(self)
        self.converter_page = ConverterPage(self)
        self.cover_page = CoverPage(self)
        self.pages = {
            AppRoute.HOME: self.home_page,
            AppRoute.CONVERTER: self.converter_page,
            AppRoute.COVER: self.cover_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.home_page.open_converter.connect(
            lambda: self.navigate(AppRoute.CONVERTER)
        )
        self.home_page.open_cover.connect(lambda: self.navigate(AppRoute.COVER))
        self.converter_page.back_requested.connect(lambda: self.navigate(AppRoute.HOME))
        self.cover_page.back_requested.connect(lambda: self.navigate(AppRoute.HOME))

        self.current_route = AppRoute.HOME
        self.navigate(AppRoute.HOME)

    @staticmethod
    def _validate_cover_payload(payload: dict[str, object]) -> dict[str, object]:
        required = {"source_path", "page_count", "trim_size_mm"}
        missing = sorted(required - payload.keys())
        if missing:
            raise ValueError("封面交接資料缺少：" + "、".join(missing))

        source_path = str(payload["source_path"]).strip()
        if not source_path:
            raise ValueError("封面交接來源路徑無效。")

        try:
            page_count = int(payload["page_count"])
        except (TypeError, ValueError) as exc:
            raise ValueError("封面交接頁數無效。") from exc
        if page_count <= 0:
            raise ValueError("封面交接頁數無效。")

        trim = payload["trim_size_mm"]
        if not isinstance(trim, dict):
            raise ValueError("封面交接成品尺寸無效。")
        try:
            width_mm = float(trim["width_mm"])
            height_mm = float(trim["height_mm"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("封面交接成品尺寸無效。") from exc
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("封面交接成品尺寸無效。")

        normalized: dict[str, Any] = dict(payload)
        normalized["source_path"] = source_path
        normalized["page_count"] = page_count
        normalized["trim_size_mm"] = {
            "width_mm": width_mm,
            "height_mm": height_mm,
        }
        return normalized

    def navigate(
        self,
        route: AppRoute,
        payload: dict[str, object] | None = None,
    ) -> None:
        if route not in self.pages:
            raise ValueError(f"未知的桌面頁面：{route}")

        if route is AppRoute.COVER and payload is not None:
            normalized = self._validate_cover_payload(payload)
            self.cover_page.open_from_conversion(normalized)

        self.stack.setCurrentWidget(self.pages[route])
        self.current_route = route
