# Desktop PySide6 Cover Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default desktop Tkinter interface with a portable PySide6 application that preserves all existing conversion features and adds a full visual cover editor on Windows, macOS, and Linux.

**Architecture:** Build a thin desktop package around the shared `epub_a4_word` core. A main window owns navigation; conversion and cover workflows use separate controllers and pages. The cover canvas uses millimetres as scene coordinates, so zoom is presentation-only and cannot change export geometry.

**Tech Stack:** Python 3.13, PySide6 6.11.1, pytest, pytest-qt, Pillow, shared cover service, `QGraphicsScene`, `QUndoStack`, `QThreadPool`.

## Global Constraints

- This plan begins only after `2026-07-24-cover-core-export.md` passes its full test gate.
- PySide6 is the default GUI on Windows, macOS, and Linux.
- `--legacy-gui` opens a Tkinter compatibility window for one release only.
- The conversion workflow retains EPUB → A4 four-up/A6 signature/A5/4×6 and DOCX → A5/4×6 behavior.
- The cover tool accepts EPUB, DOCX, and PDF independently and can also receive actual page count and trim size from a completed conversion.
- Cover edits remain in `CoverProject` schema version `1`; desktop-specific state must not be written into project geometry.
- Scene coordinates, inspector values, and serialized positions use millimetres.
- Preview may be reduced resolution; PDF/DOCX export always delegates to the shared core.
- The desktop app performs no update check.
- Search UI is added by the later search/release plan; this plan supports EPUB-embedded and local images.

---

## Part 1: Tasks 1–3

### Task 1: Create the desktop package, entry point, and dependency group

**Files:**
- Modify: `pyproject.toml`
- Create: `python/src/epub_a4_word_desktop/__init__.py`
- Create: `python/src/epub_a4_word_desktop/__main__.py`
- Create: `python/src/epub_a4_word_desktop/app.py`
- Create: `desktop/tests/test_entrypoint.py`

**Interfaces:**
- Produces console entry: `epub2a4-desktop`.
- Produces `main(argv: Sequence[str] | None = None) -> int`.
- `--legacy-gui` dispatches to `legacy_gui.run_legacy_gui()` without importing PySide6 widgets first.

- [ ] **Step 1: Add failing entry-point tests**

```python
from unittest.mock import patch

from epub_a4_word_desktop.__main__ import main


def test_default_entry_starts_qt_application():
    with patch("epub_a4_word_desktop.__main__.run_qt_app", return_value=0) as run:
        assert main([]) == 0
        run.assert_called_once_with([])


def test_legacy_flag_starts_tkinter_compatibility_gui():
    with patch("epub_a4_word_desktop.__main__.run_legacy_gui", return_value=0) as run:
        assert main(["--legacy-gui"]) == 0
        run.assert_called_once_with()
```

- [ ] **Step 2: Run the tests and verify import failure**

```bash
python3.13 -m pytest desktop/tests/test_entrypoint.py -q
```

Expected: collection ERROR because `epub_a4_word_desktop` does not exist.

- [ ] **Step 3: Add desktop packaging configuration**

Replace the existing optional-dependencies table in `pyproject.toml` and add the desktop entry point:

```toml
[project.optional-dependencies]
test = ["pytest>=8.3,<9", "pytest-qt>=4.4,<5"]
desktop = [
  "PySide6==6.11.1",
  "keyring==25.7.0",
  "platformdirs==4.10.1",
]

[project.scripts]
epub2a4-desktop = "epub_a4_word_desktop.__main__:main"
```

Do not add a second `[tool.setuptools]` or `[tool.setuptools.packages.find]` table. Keep the source-root declarations created by the core plan:

```toml
[tool.setuptools]
package-dir = {"" = "python/src"}

[tool.setuptools.packages.find]
where = ["python/src"]
```

- [ ] **Step 4: Implement explicit CLI dispatch**

```python
# python/src/epub_a4_word_desktop/__main__.py
from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="epub2a4-desktop")
    parser.add_argument("--legacy-gui", action="store_true")
    return parser


def run_qt_app(argv: list[str]) -> int:
    from .app import run
    return run(argv)


def run_legacy_gui() -> int:
    from .legacy_gui import run
    return run()


def main(argv: Sequence[str] | None = None) -> int:
    args, qt_args = build_parser().parse_known_args(list(argv) if argv is not None else None)
    if args.legacy_gui:
        return run_legacy_gui()
    return run_qt_app(qt_args)


if __name__ == "__main__":
    raise SystemExit(main())
```

`app.py` creates one `QApplication`, sets application/organization names, creates `MainWindow`, and returns `app.exec()`.

- [ ] **Step 5: Install and run tests**

```bash
python3.13 -m pip install -e '.[desktop,test]'
python3.13 -m pytest desktop/tests/test_entrypoint.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml python/src/epub_a4_word_desktop desktop/tests/test_entrypoint.py
git commit -m "feat: add PySide6 desktop application entrypoint"
```

---

### Task 2: Preserve a one-release Tkinter compatibility interface

**Files:**
- Create: `python/src/epub_a4_word_desktop/legacy_gui.py`
- Create: `python/src/epub_a4_word_desktop/conversion/legacy_adapter.py`
- Create: `desktop/tests/test_legacy_gui_logic.py`

**Interfaces:**
- Produces: `legacy_gui.run() -> int`.
- Produces pure helper `allowed_modes_for_path(path: Path) -> tuple[str, ...]`.
- Produces adapter `run_conversion(request: LegacyConversionRequest, progress) -> ConversionResult`.

- [ ] **Step 1: Write failing compatibility logic tests**

```python
from pathlib import Path

from epub_a4_word_desktop.conversion.legacy_adapter import allowed_modes_for_path


def test_legacy_epub_modes_are_preserved():
    assert allowed_modes_for_path(Path("book.epub")) == (
        "signature16", "four_up", "single_a5", "single_4x6"
    )


def test_legacy_docx_modes_are_preserved():
    assert allowed_modes_for_path(Path("book.docx")) == ("single_a5", "single_4x6")
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3.13 -m pytest desktop/tests/test_legacy_gui_logic.py -q
```

Expected: collection ERROR because the compatibility modules do not exist.

- [ ] **Step 3: Implement a conversion adapter over the shared core**

```python
@dataclass(frozen=True)
class LegacyConversionRequest:
    input_path: Path
    output_path: Path
    imposition_mode: str
    margin_mode: str
    font_name: str
    body_font_pt: float
    heading_font_pt: float
    page_numbers: bool
    cut_guides: bool


def allowed_modes_for_path(path: Path) -> tuple[str, ...]:
    if path.suffix.lower() == ".epub":
        return ("signature16", "four_up", "single_a5", "single_4x6")
    if path.suffix.lower() == ".docx":
        return ("single_a5", "single_4x6")
    return ()


def run_conversion(
    request: LegacyConversionRequest,
    progress=None,
    cancelled: Callable[[], bool] | None = None,
):
    def report(percent: int, message: str) -> None:
        if cancelled is not None and cancelled():
            raise ConversionCancelled("轉換已取消。")
        if progress is not None:
            progress(percent, message)

    settings = LayoutSettings(
        imposition_mode=request.imposition_mode,
        margin_mode=request.margin_mode,
        font_name=request.font_name,
        body_font_pt=request.body_font_pt,
        heading_font_pt=request.heading_font_pt,
        page_numbers=request.page_numbers,
        cut_guides=request.cut_guides,
    )
    return convert_input(request.input_path, request.output_path, settings, report)
```

- [ ] **Step 4: Implement the compatibility window**

The Tkinter window must contain these functional controls:

- input EPUB/DOCX picker;
- output mode constrained by `allowed_modes_for_path`;
- margin, font, body size, heading size, page-number, and cut-guide settings;
- output DOCX picker;
- progress text and cancel button;
- conversion in a background `threading.Thread`;
- errors shown with `messagebox.showerror`.

`run()` must create `tk.Tk`, build the form, call `mainloop`, and return `0` after close. It must not import PySide6.

```python
# python/src/epub_a4_word_desktop/legacy_gui.py
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .conversion.legacy_adapter import (
    LegacyConversionRequest,
    allowed_modes_for_path,
    run_conversion,
)


def run() -> int:
    root = tk.Tk()
    root.title("EPUB／Word 排版工具（舊版介面）")
    source = tk.StringVar()
    output = tk.StringVar()
    mode = tk.StringVar(value="signature16")
    status = tk.StringVar(value="請選擇 EPUB 或 DOCX。")
    margin = tk.StringVar(value="safe")
    font_name = tk.StringVar(value="Noto Serif CJK TC")
    body_font_pt = tk.DoubleVar(value=9.0)
    heading_font_pt = tk.DoubleVar(value=14.0)
    page_numbers = tk.BooleanVar(value=True)
    cut_guides = tk.BooleanVar(value=True)
    cancelled = threading.Event()

    source_entry = ttk.Entry(root, textvariable=source, width=64)
    source_entry.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

    mode_box = ttk.Combobox(root, textvariable=mode, state="readonly")
    mode_box.grid(row=1, column=0, padx=8, pady=8, sticky="ew")
    ttk.Combobox(root, textvariable=margin, values=("safe", "maximized", "borderless"), state="readonly").grid(row=2, column=0, padx=8, pady=4, sticky="ew")
    ttk.Entry(root, textvariable=font_name).grid(row=3, column=0, padx=8, pady=4, sticky="ew")
    ttk.Spinbox(root, from_=6.0, to=14.0, textvariable=body_font_pt).grid(row=4, column=0, padx=8, pady=4, sticky="ew")
    ttk.Spinbox(root, from_=8.0, to=20.0, textvariable=heading_font_pt).grid(row=5, column=0, padx=8, pady=4, sticky="ew")
    ttk.Checkbutton(root, text="顯示頁碼", variable=page_numbers).grid(row=6, column=0, sticky="w", padx=8)
    ttk.Checkbutton(root, text="顯示裁切／折線", variable=cut_guides).grid(row=7, column=0, sticky="w", padx=8)

    def choose_source() -> None:
        value = filedialog.askopenfilename(filetypes=[("Books", "*.epub *.docx")])
        if not value:
            return
        source.set(value)
        modes = allowed_modes_for_path(Path(value))
        mode_box.configure(values=modes)
        mode.set(modes[0])

    def choose_output() -> None:
        value = filedialog.asksaveasfilename(defaultextension=".docx")
        if value:
            output.set(value)

    def start() -> None:
        request = LegacyConversionRequest(
            input_path=Path(source.get()),
            output_path=Path(output.get()),
            imposition_mode=mode.get(),
            margin_mode=margin.get(),
            font_name=font_name.get(),
            body_font_pt=float(body_font_pt.get()),
            heading_font_pt=float(heading_font_pt.get()),
            page_numbers=page_numbers.get(),
            cut_guides=cut_guides.get(),
        )
        cancelled.clear()

        def worker() -> None:
            try:
                run_conversion(
                    request,
                    progress=lambda percent, text: root.after(
                        0, status.set, f"{percent}% · {text}"
                    ),
                    cancelled=cancelled.is_set,
                )
            except Exception as exc:
                root.after(0, messagebox.showerror, "轉換失敗", str(exc))
            else:
                root.after(0, status.set, "轉換完成。")

        threading.Thread(target=worker, name="legacy-conversion", daemon=True).start()

    ttk.Button(root, text="選擇來源", command=choose_source).grid(row=0, column=1, padx=8)
    ttk.Button(root, text="選擇輸出", command=choose_output).grid(row=8, column=1, padx=8)
    ttk.Entry(root, textvariable=output, width=64).grid(row=8, column=0, padx=8, pady=8)
    ttk.Button(root, text="開始轉換", command=start).grid(row=9, column=0, padx=8, pady=8)
    ttk.Button(root, text="取消", command=cancelled.set).grid(row=9, column=1, padx=8)
    ttk.Label(root, textvariable=status).grid(row=10, column=0, columnspan=2, padx=8, pady=8)
    root.columnconfigure(0, weight=1)
    root.mainloop()
    return 0
```

- [ ] **Step 5: Run tests and a manual smoke command**

```bash
python3.13 -m pytest desktop/tests/test_legacy_gui_logic.py -q
python3.13 -m epub_a4_word_desktop --legacy-gui
```

Expected: tests PASS; the compatibility window opens and closes without traceback.

- [ ] **Step 6: Commit**

```bash
git add python/src/epub_a4_word_desktop/legacy_gui.py \
  python/src/epub_a4_word_desktop/conversion desktop/tests/test_legacy_gui_logic.py
git commit -m "feat: retain one-release Tkinter compatibility GUI"
```

---

### Task 3: Build the PySide6 main shell and navigation

**Files:**
- Create: `python/src/epub_a4_word_desktop/main_window.py`
- Create: `python/src/epub_a4_word_desktop/pages/home_page.py`
- Create: `python/src/epub_a4_word_desktop/pages/__init__.py`
- Modify: `python/src/epub_a4_word_desktop/app.py`
- Create: `desktop/tests/test_main_window.py`

**Interfaces:**
- Produces: `MainWindow.navigate(route: AppRoute, payload: dict | None = None)`.
- Routes: `HOME`, `CONVERTER`, `COVER`.
- Home exposes buttons `轉換 EPUB／Word` and `封面工具`.

- [ ] **Step 1: Write failing Qt navigation tests**

```python
from epub_a4_word_desktop.main_window import AppRoute, MainWindow


def test_home_is_initial_route(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.current_route is AppRoute.HOME


def test_navigation_switches_to_cover_page(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.navigate(AppRoute.COVER)
    assert window.current_route is AppRoute.COVER
    assert window.stack.currentWidget().objectName() == "cover-page"
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_main_window.py -q
```

Expected: collection ERROR because `main_window.py` does not exist.

- [ ] **Step 3: Implement typed routes and page ownership**

```python
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
        self.setCentralWidget(self.stack)
        self.pages = {
            AppRoute.HOME: HomePage(),
            AppRoute.CONVERTER: ConverterPage(),
            AppRoute.COVER: CoverPage(),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.current_route = AppRoute.HOME
        self.navigate(AppRoute.HOME)
```

Connect page signals rather than passing the entire main window into child pages:

```python
self.pages[AppRoute.HOME].open_converter.connect(lambda: self.navigate(AppRoute.CONVERTER))
self.pages[AppRoute.HOME].open_cover.connect(lambda: self.navigate(AppRoute.COVER))
```

- [ ] **Step 4: Add route payload handling**

`navigate(AppRoute.COVER, payload)` calls `CoverPage.open_from_conversion(payload)` only when payload includes `source_path`, `page_count`, and `trim_size_mm`. Invalid payloads raise `ValueError` before switching pages.

```python
def navigate(self, route: AppRoute, payload: dict[str, object] | None = None) -> None:
    if route is AppRoute.COVER and payload is not None:
        required = {"source_path", "page_count", "trim_size_mm"}
        missing = sorted(required - payload.keys())
        if missing:
            raise ValueError("封面交接資料缺少：" + "、".join(missing))
        page_count = int(payload["page_count"])
        trim = payload["trim_size_mm"]
        if page_count <= 0 or not isinstance(trim, dict):
            raise ValueError("封面交接頁數或成品尺寸無效。")
        self.cover_page.open_from_conversion(payload)
    self.stack.setCurrentWidget(self.pages[route])
    self.current_route = route
```

- [ ] **Step 5: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests/test_main_window.py -q
git add python/src/epub_a4_word_desktop/main_window.py \
  python/src/epub_a4_word_desktop/pages python/src/epub_a4_word_desktop/app.py \
  desktop/tests/test_main_window.py
git commit -m "feat: add desktop navigation shell"
```

Expected: PASS.

---
