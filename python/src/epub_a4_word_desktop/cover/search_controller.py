from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
from typing import Mapping

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from epub_a4_word.cover.search import (
    GeneralCoverSearch,
    GoogleBooksProvider,
    GoogleCustomSearchProvider,
    ImageDownloadError,
    JsonHttpClient,
    OpenLibraryProvider,
    ProviderCredential,
    PublicBookSearch,
    SearchCandidate,
    SearchCredentialError,
    SearchKind,
    SearchQuotaError,
    SearchTimeoutError,
    download_candidate,
)
from epub_a4_word.cover.search.models import CoverSearchRequest

from ..settings.credentials import LayeredCredentialStore

ERROR_MESSAGES = {
    SearchCredentialError: "Google 圖片搜尋憑證無效，請重新設定。",
    SearchTimeoutError: "搜尋逾時，請檢查網路後重試。",
    ImageDownloadError: "選取的圖片無法下載或格式不受支援。",
}


def _message_for(exc: Exception) -> str:
    if isinstance(exc, SearchQuotaError):
        return str(exc) or "搜尋服務暫時限制請求，請稍後重試。"
    return next((text for kind, text in ERROR_MESSAGES.items() if isinstance(exc, kind)), str(exc))


class SharedSearchFacade:
    def __init__(self, http_client: JsonHttpClient | None = None) -> None:
        self.http = http_client or JsonHttpClient()
        self.public = PublicBookSearch(
            (GoogleBooksProvider(self.http), OpenLibraryProvider(self.http))
        )
        self.general = GeneralCoverSearch(GoogleCustomSearchProvider(self.http))

    def search_public(self, metadata: Mapping[str, object]):
        return self.public.search(
            CoverSearchRequest(
                kind=SearchKind.FRONT,
                isbn=str(metadata.get("isbn", "")),
                title=str(metadata.get("title", "")),
                author=str(metadata.get("author", "")),
                locale=str(metadata.get("language", "") or "zh-TW"),
                max_results=20,
            )
        )

    def search_general(
        self,
        metadata: Mapping[str, object],
        credential: ProviderCredential,
    ):
        return self.general.search_all(
            title=str(metadata.get("title", "")),
            author=str(metadata.get("author", "")),
            isbn=str(metadata.get("isbn", "")),
            locale=str(metadata.get("language", "") or "zh-TW"),
            credential=credential,
            max_results=10,
        )

    def download(self, candidate: SearchCandidate, destination: Path):
        return download_candidate(candidate, destination, self.http)


class WorkerSignals(QObject):
    completed = Signal(int, str, object)
    failed = Signal(int, str, str)


class SearchWorker(QRunnable):
    def __init__(self, generation: int, mode: str, callable_) -> None:
        super().__init__()
        self.generation = generation
        self.mode = mode
        self.callable = callable_
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.callable()
        except Exception as exc:
            self.signals.failed.emit(self.generation, self.mode, _message_for(exc))
        else:
            self.signals.completed.emit(self.generation, self.mode, result)


class SearchController(QObject):
    results_ready = Signal(str, object)
    search_failed = Signal(str, str)
    credential_required = Signal()
    download_ready = Signal(str, object)
    download_failed = Signal(str)

    def __init__(
        self,
        service: SharedSearchFacade | None = None,
        credential_store: LayeredCredentialStore | None = None,
        pool=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or SharedSearchFacade()
        self.credential_store = credential_store
        self.pool = pool or QThreadPool.globalInstance()
        self._search_generations = {"public": 0, "general": 0}
        self._download_generation = 0
        self._workers: set[QRunnable] = set()

    def stored_credential(self) -> ProviderCredential | None:
        return self.credential_store.load() if self.credential_store else None

    def save_session_credential(self, value: ProviderCredential) -> None:
        if self.credential_store is None:
            raise RuntimeError("憑證儲存尚未初始化。")
        self.credential_store.save_session(value)

    def save_persistent_credential(self, value: ProviderCredential, **kwargs) -> None:
        if self.credential_store is None:
            raise RuntimeError("憑證儲存尚未初始化。")
        self.credential_store.save_persistent(value, **kwargs)

    def clear_credentials(self) -> None:
        if self.credential_store:
            self.credential_store.clear()

    def search_public(self, metadata: Mapping[str, object]) -> None:
        self._start_search("public", lambda: self.service.search_public(metadata))

    def search_general(
        self,
        metadata: Mapping[str, object],
        credential: ProviderCredential | None = None,
    ) -> None:
        value = credential or self.stored_credential()
        if value is None or not value.complete:
            self.credential_required.emit()
            return
        self._start_search("general", lambda: self.service.search_general(metadata, value))

    def _start_search(self, mode: str, callable_) -> None:
        self._search_generations[mode] = self._search_generations.get(mode, 0) + 1
        generation = self._search_generations[mode]
        worker = SearchWorker(generation, mode, callable_)
        worker.signals.completed.connect(self._search_completed)
        worker.signals.failed.connect(self._search_failed)
        self._workers.add(worker)
        self.pool.start(worker)

    @Slot(int, str, object)
    def _search_completed(self, generation: int, mode: str, response) -> None:
        if generation != self._search_generations.get(mode):
            return
        self.results_ready.emit(mode, response)

    @Slot(int, str, str)
    def _search_failed(self, generation: int, mode: str, message: str) -> None:
        if generation != self._search_generations.get(mode):
            return
        self.search_failed.emit(mode, message)

    @staticmethod
    def _safe_filename(candidate: SearchCandidate, index: int) -> str:
        name = re.sub(r"[^0-9A-Za-z._-]+", "_", candidate.candidate_id).strip("._")
        extension = {
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/tiff": ".tiff",
            "image/bmp": ".bmp",
        }.get(candidate.media_type.casefold(), ".jpg")
        return f"search-{index:02d}-{name[:60] or 'candidate'}{extension}"

    def download_selected(
        self,
        selections: Mapping[str, SearchCandidate],
        assets_dir: Path | str,
        mode: str,
    ) -> None:
        self._download_generation += 1
        generation = self._download_generation
        destination_root = Path(assets_dir) / "search"
        destination_root.mkdir(parents=True, exist_ok=True)

        def work():
            paths: dict[str, Path] = {}
            for index, (category, candidate) in enumerate(selections.items(), start=1):
                destination = destination_root / self._safe_filename(candidate, index)
                paths[category] = self.service.download(candidate, destination).path
            return paths

        worker = SearchWorker(generation, f"download:{mode}", work)
        worker.signals.completed.connect(self._download_completed)
        worker.signals.failed.connect(self._download_failed)
        self._workers.add(worker)
        self.pool.start(worker)

    @Slot(int, str, object)
    def _download_completed(self, generation: int, mode: str, paths) -> None:
        if generation != self._download_generation:
            return
        self.download_ready.emit(mode.removeprefix("download:"), paths)

    @Slot(int, str, str)
    def _download_failed(self, generation: int, _mode: str, message: str) -> None:
        if generation == self._download_generation:
            self.download_failed.emit(message)
