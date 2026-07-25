from __future__ import annotations

import threading
from pathlib import Path

from .conversion.legacy_adapter import (
    ConversionCancelled,
    LegacyConversionRequest,
    allowed_modes_for_path,
    run_conversion,
)


def run() -> int:
    """Open the one-release Tkinter compatibility interface."""

    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("EPUB／Word 排版工具（舊版介面）")
    root.minsize(700, 500)

    source = tk.StringVar()
    output = tk.StringVar()
    mode = tk.StringVar(value="signature16")
    status = tk.StringVar(value="請選擇 EPUB 或 DOCX。")
    progress_value = tk.IntVar(value=0)
    margin = tk.StringVar(value="safe")
    font_name = tk.StringVar(value="Noto Serif CJK TC")
    body_font_pt = tk.DoubleVar(value=9.0)
    heading_font_pt = tk.DoubleVar(value=14.0)
    page_numbers = tk.BooleanVar(value=True)
    cut_guides = tk.BooleanVar(value=True)
    cancelled = threading.Event()

    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="來源檔案").grid(row=0, column=0, sticky="w", pady=4)
    source_entry = ttk.Entry(frame, textvariable=source)
    source_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

    ttk.Label(frame, text="輸出模式").grid(row=1, column=0, sticky="w", pady=4)
    mode_box = ttk.Combobox(frame, textvariable=mode, state="readonly")
    mode_box.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

    ttk.Label(frame, text="邊界模式").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Combobox(
        frame,
        textvariable=margin,
        values=("safe", "maximized", "borderless"),
        state="readonly",
    ).grid(row=2, column=1, sticky="ew", padx=8, pady=4)

    ttk.Label(frame, text="字型").grid(row=3, column=0, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=font_name).grid(
        row=3, column=1, sticky="ew", padx=8, pady=4
    )

    ttk.Label(frame, text="內文字級").grid(row=4, column=0, sticky="w", pady=4)
    ttk.Spinbox(
        frame, from_=6.0, to=14.0, increment=0.5, textvariable=body_font_pt
    ).grid(row=4, column=1, sticky="ew", padx=8, pady=4)

    ttk.Label(frame, text="標題字級").grid(row=5, column=0, sticky="w", pady=4)
    ttk.Spinbox(
        frame, from_=8.0, to=24.0, increment=0.5, textvariable=heading_font_pt
    ).grid(row=5, column=1, sticky="ew", padx=8, pady=4)

    ttk.Checkbutton(frame, text="顯示頁碼", variable=page_numbers).grid(
        row=6, column=1, sticky="w", padx=8, pady=4
    )
    ttk.Checkbutton(frame, text="顯示裁切／折線", variable=cut_guides).grid(
        row=7, column=1, sticky="w", padx=8, pady=4
    )

    ttk.Label(frame, text="輸出 DOCX").grid(row=8, column=0, sticky="w", pady=4)
    ttk.Entry(frame, textvariable=output).grid(
        row=8, column=1, sticky="ew", padx=8, pady=4
    )

    progress_bar = ttk.Progressbar(
        frame, maximum=100, variable=progress_value, mode="determinate"
    )
    progress_bar.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(16, 4))
    ttk.Label(frame, textvariable=status).grid(
        row=11, column=0, columnspan=3, sticky="w", pady=4
    )

    def choose_source() -> None:
        value = filedialog.askopenfilename(
            title="選擇 EPUB 或 DOCX",
            filetypes=[("EPUB／Word", "*.epub *.docx")],
        )
        if not value:
            return
        source.set(value)
        modes = allowed_modes_for_path(Path(value))
        mode_box.configure(values=modes)
        mode.set(modes[0] if modes else "")
        if not output.get():
            output.set(str(Path(value).with_suffix(".converted.docx")))

    def choose_output() -> None:
        value = filedialog.asksaveasfilename(
            title="選擇輸出 DOCX",
            defaultextension=".docx",
            filetypes=[("Word 文件", "*.docx")],
        )
        if value:
            output.set(value)

    def set_progress(percent: int, text: str) -> None:
        progress_value.set(percent)
        status.set(f"{percent}% · {text}")

    def start() -> None:
        input_path = Path(source.get()).expanduser()
        output_path = Path(output.get()).expanduser()
        if not source.get() or not input_path.is_file():
            messagebox.showerror("無法開始", "請選擇存在的 EPUB 或 DOCX 檔案。")
            return
        if not output.get():
            messagebox.showerror("無法開始", "請選擇輸出 DOCX 路徑。")
            return

        request = LegacyConversionRequest(
            input_path=input_path,
            output_path=output_path,
            imposition_mode=mode.get(),
            margin_mode=margin.get(),
            font_name=font_name.get(),
            body_font_pt=float(body_font_pt.get()),
            heading_font_pt=float(heading_font_pt.get()),
            page_numbers=page_numbers.get(),
            cut_guides=cut_guides.get(),
        )
        cancelled.clear()
        progress_value.set(0)
        status.set("正在準備轉換…")
        start_button.configure(state="disabled")

        def finish() -> None:
            start_button.configure(state="normal")

        def worker() -> None:
            try:
                run_conversion(
                    request,
                    progress=lambda percent, text: root.after(
                        0, set_progress, percent, text
                    ),
                    cancelled=cancelled.is_set,
                )
            except ConversionCancelled:
                root.after(0, status.set, "轉換已取消。")
            except Exception as exc:
                root.after(
                    0,
                    lambda: messagebox.showerror("轉換失敗", str(exc), parent=root),
                )
                root.after(0, status.set, "轉換失敗。")
            else:
                root.after(0, progress_value.set, 100)
                root.after(0, status.set, "轉換完成。")
            finally:
                root.after(0, finish)

        threading.Thread(
            target=worker,
            name="legacy-conversion",
            daemon=True,
        ).start()

    ttk.Button(frame, text="選擇來源", command=choose_source).grid(
        row=0, column=2, padx=4, pady=4
    )
    ttk.Button(frame, text="選擇輸出", command=choose_output).grid(
        row=8, column=2, padx=4, pady=4
    )
    start_button = ttk.Button(frame, text="開始轉換", command=start)
    start_button.grid(row=9, column=1, sticky="e", padx=8, pady=12)
    ttk.Button(frame, text="取消", command=cancelled.set).grid(
        row=9, column=2, padx=4, pady=12
    )

    def close() -> None:
        cancelled.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    source_entry.focus_set()
    root.mainloop()
    return 0
