# Cover Search, Credentials, and Portable Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in cover search with multiple candidates, secure local credential handling, validated image download/cache, and portable Windows/macOS/Linux release artifacts while preserving independent Android packaging.

**Architecture:** Implement provider request/response normalization in the shared Python package so Android and desktop interpret Google Books, Open Library, and Google Custom Search identically. Platform layers own credentials and user interaction, pass credentials only for one request, display source/use-right warnings, and copy a selected image into the current cover project before editing.

**Tech Stack:** Python 3.13 stdlib HTTPS/JSON, Pillow, pytest; Google Books API, Open Library APIs, Google Custom Search JSON API; Android Keystore AES-GCM, Compose, Coil 3.5.0; desktop keyring 25.7.0, platformdirs 4.10.1; PyInstaller, AppImage tooling, GitHub Actions.

## Global Constraints

- This plan starts after the shared core, desktop editor, and Android editor plans pass.
- Search order: ISBN in public book databases, title+author in public book databases, then optional general image search.
- Public providers: Google Books and Open Library.
- General image provider in the first release: Google Custom Search image mode.
- General search requires a user-supplied API Key and Search Engine ID; no shared credential may appear in source, APK, desktop package, CI logs, fixtures, or crash output.
- Search shows multiple candidates and never auto-selects the first result.
- General image search occurs only after the user explicitly switches to it and presses Search.
- All requests use HTTPS and bounded timeouts.
- Source EPUB/DOCX/PDF files are never uploaded; requests contain only ISBN, title, author, locale, or user-entered keywords.
- Search failure never disables local/embedded cover creation.
- Selected image downloads are limited to 50 MiB and 20,000 × 20,000 decoded pixels.
- UI displays source page and `授權狀態未確認；使用者需自行確認使用權` unless a provider supplies an explicit rights value.
- Android network permission is added only in this plan.
- Desktop packages are portable and perform no version check or automatic update.
- Standard desktop mode stores settings in platform user-data directories; portable mode activates with `portable.flag` and writes beneath `data/`.

---

## Subpart B: Tasks 7–8

### Task 7: Add desktop standard/portable paths and credential storage

**Files:**
- Create: `python/src/epub_a4_word_desktop/settings/paths.py`
- Create: `python/src/epub_a4_word_desktop/settings/credentials.py`
- Create: `python/src/epub_a4_word_desktop/settings/models.py`
- Create: `desktop/tests/test_settings_paths.py`
- Create: `desktop/tests/test_credentials.py`

**Interfaces:**
- Produces `AppPaths.detect(executable_dir) -> AppPaths`.
- `portable.flag` activates portable mode.
- Standard credentials use keyring service `epub2a4-cover-search`; portable credentials default to session-only and may be saved plaintext only after explicit confirmation.

- [ ] **Step 1: Write failing path and credential tests**

```python
def test_portable_flag_uses_sibling_data_directory(tmp_path):
    (tmp_path / "portable.flag").write_text("1", encoding="ascii")
    paths = AppPaths.detect(tmp_path)
    assert paths.portable is True
    assert paths.config_dir == tmp_path / "data/config"
    assert paths.cache_dir == tmp_path / "data/cache"


def test_standard_mode_uses_platformdirs(monkeypatch, tmp_path):
    monkeypatch.setattr("platformdirs.user_config_path", lambda *a, **k: tmp_path / "config")
    paths = AppPaths.detect(tmp_path)
    assert paths.portable is False
    assert paths.config_dir == tmp_path / "config"


def test_portable_store_refuses_persistence_without_confirmation(tmp_path):
    store = PortableCredentialStore(tmp_path / "credentials.json")
    with pytest.raises(CredentialPersistenceWarning):
        store.save(SearchCredential("key", "cx"), confirmed_plaintext=False)
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_settings_paths.py desktop/tests/test_credentials.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement platform and portable paths**

Use `platformdirs.user_config_path`, `user_cache_path`, and `user_data_path` with app name `EPUB2A4`. In portable mode, verify `data/` is writable by creating/deleting a probe file. If not writable, raise `PortableModeUnavailable` and offer standard-mode restart through UI.

```python
@dataclass(frozen=True)
class RuntimePaths:
    mode: str
    config_dir: Path
    cache_dir: Path
    data_dir: Path


class PortableModeUnavailable(RuntimeError):
    """Raised when portable data cannot be created beside the executable."""


def resolve_runtime_paths(executable_dir: Path) -> RuntimePaths:
    portable_flag = executable_dir / "portable.flag"
    if portable_flag.is_file():
        data = executable_dir / "data"
        data.mkdir(parents=True, exist_ok=True)
        probe = data / ".write-probe"
        try:
            probe.write_bytes(b"ok")
        except OSError as exc:
            raise PortableModeUnavailable("可攜模式資料夾不可寫入。") from exc
        finally:
            probe.unlink(missing_ok=True)
        return RuntimePaths("portable", data / "config", data / "cache", data / "projects")
    return RuntimePaths(
        "standard",
        Path(user_config_path("EPUB2A4", ensure_exists=True)),
        Path(user_cache_path("EPUB2A4", ensure_exists=True)),
        Path(user_data_path("EPUB2A4", ensure_exists=True)),
    )
```

- [ ] **Step 4: Implement credential backends**

- `KeyringCredentialStore`: API key stored as password under username `api-key`; CX stored under `search-engine-id`.
- `SessionCredentialStore`: in-memory only.
- `PortableCredentialStore`: JSON with restrictive permissions where supported; UI warning remains mandatory.
- Never fall back from failed keyring to plaintext automatically; fall back to session-only and show a warning.

```python
SERVICE_NAME = "EPUB2A4 Google Image Search"


class KeyringCredentialStore:
    def load(self) -> ProviderCredential | None:
        api_key = keyring.get_password(SERVICE_NAME, "api-key")
        search_engine_id = keyring.get_password(SERVICE_NAME, "search-engine-id")
        if not api_key or not search_engine_id:
            return None
        return ProviderCredential(api_key=api_key, search_engine_id=search_engine_id)

    def save(self, value: ProviderCredential) -> None:
        keyring.set_password(SERVICE_NAME, "api-key", value.api_key)
        keyring.set_password(SERVICE_NAME, "search-engine-id", value.search_engine_id)

    def clear(self) -> None:
        for username in ("api-key", "search-engine-id"):
            try:
                keyring.delete_password(SERVICE_NAME, username)
            except keyring.errors.PasswordDeleteError:
                continue


class SessionCredentialStore:
    def __init__(self) -> None:
        self.value: ProviderCredential | None = None


class PortableCredentialStore:
    def __init__(self, path: Path, confirmed_plaintext: bool) -> None:
        if not confirmed_plaintext:
            raise PermissionError("未確認可攜模式明文憑證風險。")
        self.path = path

    def save(self, value: ProviderCredential) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(value)), "utf-8")
        if os.name == "posix":
            self.path.chmod(0o600)
```

- [ ] **Step 5: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_settings_paths.py desktop/tests/test_credentials.py -q
git add python/src/epub_a4_word_desktop/settings desktop/tests
git commit -m "feat: add desktop portable paths and credential stores"
```

Expected: PASS.

---

### Task 8: Add desktop multi-candidate search panel

**Files:**
- Create: `python/src/epub_a4_word_desktop/cover/search_controller.py`
- Create: `python/src/epub_a4_word_desktop/cover/search_panel.py`
- Create: `python/src/epub_a4_word_desktop/cover/credential_dialog.py`
- Modify: `python/src/epub_a4_word_desktop/pages/cover_page.py`
- Create: `desktop/tests/test_search_controller.py`
- Create: `desktop/tests/test_search_panel.py`

**Interfaces:**
- Search controller runs shared service off the UI thread.
- Panel supports public database and general image tabs.
- Candidate selection downloads through shared validation then adds the asset to the current project.

- [ ] **Step 1: Write failing controller tests**

```python
def test_public_search_passes_no_credentials(qtbot, fake_service):
    controller = SearchController(fake_service, credential_store=EmptyCredentialStore())
    with qtbot.waitSignal(controller.results_ready):
        controller.search_public(title="範例書", author="作者", isbn="")
    assert "credential" not in fake_service.last_request or not fake_service.last_request["credential"]["api_key"]


def test_general_search_prompts_when_credential_missing(qtbot, fake_service):
    controller = SearchController(fake_service, credential_store=EmptyCredentialStore())
    with qtbot.waitSignal(controller.credential_required):
        controller.search_general("範例書 封面")
    assert fake_service.calls == 0
```

- [ ] **Step 2: Run tests and verify failure**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_search_controller.py desktop/tests/test_search_panel.py -q
```

Expected: collection ERROR.

- [ ] **Step 3: Implement asynchronous search/download workers**

Use `QThreadPool`. Every request receives a generation ID; ignore results after query changes or page closes. Map credential/quota/timeout/no-result/decode errors to distinct Traditional Chinese messages.

```python
ERROR_MESSAGES = {
    MissingCredentialError: "請先輸入 API Key 與 Search Engine ID。",
    SearchQuotaError: "搜尋配額已用完，請稍後重試或更換 API Key。",
    SearchTimeoutError: "搜尋逾時，請檢查網路後重試。",
    NoSearchResultsError: "找不到候選封面。",
    InvalidImageError: "選取的檔案不是可用圖片。",
}


class SearchWorker(QRunnable):
    def __init__(self, generation: int, request: CoverSearchRequest, credential, service) -> None:
        super().__init__()
        self.generation = generation
        self.request = request
        self.credential = credential
        self.service = service
        self.signals = SearchSignals()

    def run(self) -> None:
        try:
            candidates = self.service.search(self.request, self.credential)
        except Exception as exc:
            message = next((text for kind, text in ERROR_MESSAGES.items() if isinstance(exc, kind)), str(exc))
            self.signals.failed.emit(self.generation, message)
        else:
            self.signals.completed.emit(self.generation, candidates)


class SearchController(QObject):
    def start(self, request, credential) -> None:
        self.generation += 1
        self.pool.start(SearchWorker(self.generation, request, credential, self.service))

    def accept_results(self, generation: int, candidates: list[SearchCandidate]) -> None:
        if generation == self.generation and self.active:
            self.results_ready.emit(candidates)
```

- [ ] **Step 4: Build candidate cards and source actions**

Use a scrollable grid which reflows with width. Each card shows preview, dimensions, provider, source, rights warning, and Select. Open source pages with `QDesktopServices.openUrl` only after validating HTTPS.

```python
class CandidateCard(QFrame):
    selected = Signal(SearchCandidate)

    def __init__(self, candidate: SearchCandidate) -> None:
        super().__init__()
        self.candidate = candidate
        layout = QVBoxLayout(self)
        self.preview = QLabel()
        self.preview.setFixedSize(160, 220)
        self.preview.setScaledContents(True)
        layout.addWidget(self.preview)
        layout.addWidget(QLabel(candidate.title or QUrl(candidate.source_page).host()))
        dimensions = f"{candidate.width} × {candidate.height}" if candidate.width and candidate.height else "解析度未知"
        layout.addWidget(QLabel(dimensions))
        layout.addWidget(QLabel(candidate.provider))
        layout.addWidget(QLabel(candidate.rights_text or "授權狀態未確認；使用者需自行確認使用權"))
        source_button = QPushButton("查看來源")
        source_button.clicked.connect(self._open_source)
        layout.addWidget(source_button)
        choose_button = QPushButton("選擇")
        choose_button.clicked.connect(lambda: self.selected.emit(candidate))
        layout.addWidget(choose_button)

    def _open_source(self) -> None:
        url = QUrl(self.candidate.source_page)
        if url.scheme().lower() != "https":
            QMessageBox.warning(self, "無法開啟", "來源網址不是 HTTPS。")
            return
        QDesktopServices.openUrl(url)
```

```python
class CandidateGrid(QWidget):
    def resizeEvent(self, event) -> None:
        columns = max(1, self.width() // 190)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        super().resizeEvent(event)
```

- [ ] **Step 5: Add credential dialog behavior**

Options: Save to system credential store, Use this time, and in portable mode Save in portable data folder with a second confirmation dialog describing plaintext risk.

```python
class CredentialDialog(QDialog):
    credential_chosen = Signal(ProviderCredential, str)

    def accept_system(self) -> None:
        credential = self._validated_value()
        self.credential_chosen.emit(credential, "system")
        self.accept()

    def accept_session(self) -> None:
        credential = self._validated_value()
        self.credential_chosen.emit(credential, "session")
        self.accept()

    def accept_portable(self) -> None:
        answer = QMessageBox.warning(
            self,
            "可攜模式憑證風險",
            "API Key 將儲存在可攜資料夾，取得該資料夾的人可能讀取憑證。仍要儲存嗎？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.credential_chosen.emit(self._validated_value(), "portable")
            self.accept()

    def _validated_value(self) -> ProviderCredential:
        api_key = self.api_key.text().strip()
        search_engine_id = self.search_engine_id.text().strip()
        if not api_key or not search_engine_id:
            raise ValueError("API Key 與 Search Engine ID 都必須填寫。")
        return ProviderCredential(api_key, search_engine_id)
```

- [ ] **Step 6: Add selected image to editor**

Download to current project assets directory, then ask front-only/full-spread. Push the resulting project mutation through `QUndoStack` so selection is undoable.

```python
def choose_candidate(self, candidate: SearchCandidate) -> None:
    destination = self.controller.assets_dir / f"candidate-{candidate.id}.img"
    worker = DownloadWorker(candidate, destination, self.service)
    worker.signals.completed.connect(lambda path: self._choose_mode(candidate, path))
    worker.signals.failed.connect(self.error.emit)
    self.pool.start(worker)


def _choose_mode(self, candidate: SearchCandidate, path: Path) -> None:
    box = QMessageBox(self)
    box.setWindowTitle("圖片套用方式")
    front = box.addButton("只放正面", QMessageBox.AcceptRole)
    spread = box.addButton("延伸到完整書封", QMessageBox.AcceptRole)
    box.addButton(QMessageBox.Cancel)
    box.exec()
    if box.clickedButton() not in (front, spread):
        return
    mode = ImageMode.FRONT_ONLY if box.clickedButton() is front else ImageMode.FULL_SPREAD
    before = self.controller.project_json
    after = patch_cover_art(before, path, mode)
    self.controller.undo_stack.push(ReplaceProjectCommand(self.controller, before, after, "選擇封面圖片"))
```

- [ ] **Step 7: Run tests and commit**

```bash
QT_QPA_PLATFORM=offscreen python3.13 -m pytest \
  desktop/tests/test_search_controller.py desktop/tests/test_search_panel.py -q
git add python/src/epub_a4_word_desktop/cover \
  python/src/epub_a4_word_desktop/pages/cover_page.py desktop/tests
git commit -m "feat: add desktop multi-candidate cover search"
```

Expected: PASS.

---
