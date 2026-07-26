from __future__ import annotations

import threading
from typing import Protocol

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from epub_a4_word.converter import convert_input

from .legacy_adapter import ConversionCancelled
from .models import ConversionCompletion, ConversionRequest, make_completion


class WorkerPool(Protocol):
    def start(self, worker: QRunnable) -> None: ...


class ConversionWorkerSignals(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class ConversionWorker(QRunnable):
    def __init__(self, request: ConversionRequest, cancelled: threading.Event) -> None:
        super().__init__()
        self.request = request
        self.cancelled_event = cancelled
        self.signals = ConversionWorkerSignals()

    def _check_cancelled(self) -> None:
        if self.cancelled_event.is_set():
            raise ConversionCancelled("轉換已取消。")

    def _progress(self, percent: int, message: str) -> None:
        self._check_cancelled()
        self.signals.progress.emit(int(percent), str(message))

    @Slot()
    def run(self) -> None:
        try:
            self._check_cancelled()
            result = convert_input(
                self.request.input_path,
                self.request.output_path,
                self.request.to_layout_settings(),
                self._progress,
                content_only=self.request.content_only,
            )
            self._check_cancelled()
        except ConversionCancelled:
            self.signals.cancelled.emit()
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.completed.emit(make_completion(self.request, result))


class ConversionController(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        pool: WorkerPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.pool: WorkerPool = pool or QThreadPool.globalInstance()
        self._cancelled = threading.Event()
        self._worker: ConversionWorker | None = None
        self.is_running = False

    def start(self, request: ConversionRequest) -> None:
        request.validate()
        if self.is_running:
            raise RuntimeError("已有轉換工作正在執行。")

        self._cancelled = threading.Event()
        worker = ConversionWorker(request, self._cancelled)
        worker.signals.progress.connect(self.progress.emit)
        worker.signals.completed.connect(self._on_completed)
        worker.signals.failed.connect(self._on_failed)
        worker.signals.cancelled.connect(self._on_cancelled)
        self._worker = worker
        self.is_running = True
        self.pool.start(worker)

    def cancel(self) -> None:
        if self.is_running:
            self._cancelled.set()

    @Slot(object)
    def _on_completed(self, completion: ConversionCompletion) -> None:
        self._finish()
        self.completed.emit(completion)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._finish()
        self.failed.emit(message)

    @Slot()
    def _on_cancelled(self) -> None:
        self._finish()
        self.cancelled.emit()

    def _finish(self) -> None:
        self.is_running = False
        self._worker = None
