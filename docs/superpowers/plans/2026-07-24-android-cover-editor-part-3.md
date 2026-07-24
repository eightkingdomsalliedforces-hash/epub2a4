# Android Compose Cover Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Android cover workflow which opens EPUB/DOCX/PDF, confirms physical book settings, applies a local template, permits touch-based fine tuning, and saves independent PDF plus DOCX files.

**Architecture:** Keep Kotlin/Compose responsible for route state, SAF access, touch gestures, forms, and local credential ownership. Call the shared Python cover service through a dedicated gateway which exchanges schema-versioned JSON and runs export/render operations on the existing large-stack execution mechanism.

**Tech Stack:** Kotlin/JVM 17, Jetpack Compose Material 3, Android API 24+, Chaquopy Python 3.13, StateFlow, SAF/DocumentsContract, JUnit 4, Compose UI tests.

## Global Constraints

- This plan begins only after `2026-07-24-cover-core-export.md` passes.
- Minimum Android version stays API 24 and ABI stays arm64-v8a.
- Conversion remains available while the cover tool is added.
- Cover tool inputs: EPUB, DOCX, PDF.
- Online search is not implemented in this plan; EPUB-embedded and local images work offline.
- Android does not generate artwork.
- Project JSON remains schema version `1` and all geometry values are millimetres.
- Page count must be explicitly confirmed before creating or exporting a cover.
- Default bleed is 3 mm, overlap is fixed at 5 mm.
- The app creates two independent files in a user-selected SAF directory.
- Export defaults to 300 DPI and offers an explicit 200 DPI low-memory choice; it never silently lowers DPI.
- Python render/export work must not run on the main thread or a small coroutine worker stack.
- Until the later search plan, the manifest still contains no `INTERNET` permission.

---

## Part 3: Tasks 9–11

### Task 9: Export PDF and DOCX to a selected directory

**Files:**
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewModel.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/ExportCoverDialog.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/MainActivity.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt`
- Create: `app/src/test/java/tw/daniel/epubword/cover/ui/CoverExportStateTest.kt`

**Interfaces:**
- User chooses 300 or 200 DPI before export.
- Python creates both local files; UI then requests a directory.
- Save state distinguishes complete, partial, cancelled, and failed.

- [ ] **Step 1: Write failing export-state tests**

```kotlin
@Test fun cannotSaveBeforeBothLocalExportsExist() {
    val state = CoverUiState(status = CoverStatus.EDITING)
    assertFalse(state.canChooseExportDirectory)
}

@Test fun partialSaveNamesTheSuccessfulFile() {
    val result = SavedCoverFiles(pdfUri = fakePdfUri, docxUri = null)
    assertEquals("PDF 已儲存；DOCX 儲存失敗，可重試。", result.userMessage)
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.ui.CoverExportStateTest'
```

Expected: compilation failure.

- [ ] **Step 3: Implement export preparation**

Call gateway `export` on the large-stack executor. Catch `OutOfMemoryError` and show:

```text
300 DPI 匯出需要更多記憶體。請關閉其他 App 後重試，或明確選擇 200 DPI。
```

Do not automatically retry at 200 DPI.

```kotlin
fun prepareExport(dpi: Int) {
    require(dpi == 200 || dpi == 300)
    val files = workingFiles ?: return
    val projectJson = currentProjectJson ?: return
    viewModelScope.launch {
        _uiState.update { it.copy(status = CoverStatus.EXPORTING, errorMessage = null) }
        try {
            val pdf = File(files.exportDir, coverExportName(_uiState.value.metadata.title, "pdf"))
            val docx = File(files.exportDir, coverExportName(_uiState.value.metadata.title, "docx"))
            gateway.export(projectJson, pdf, docx, dpi)
            pendingExports = PendingCoverExports(pdf, docx, sanitizeTitle(_uiState.value.metadata.title))
            _uiState.update {
                it.copy(status = CoverStatus.READY_TO_SAVE, exportDirectoryRequestId = it.exportDirectoryRequestId + 1)
            }
        } catch (failure: OutOfMemoryError) {
            _uiState.update {
                it.copy(
                    status = CoverStatus.EDITING,
                    errorMessage = "300 DPI 匯出需要更多記憶體。請關閉其他 App 後重試，或明確選擇 200 DPI。",
                )
            }
        } catch (failure: Throwable) {
            _uiState.update {
                it.copy(status = CoverStatus.EDITING, errorMessage = failure.message ?: "封面匯出失敗。")
            }
        }
    }
}
```

- [ ] **Step 4: Add directory picker and paired save**

`MainActivity` registers `ActivityResultContracts.OpenDocumentTree`. After successful local export, `AppRoot` launches it once. Pass result to `CoverViewModel.saveExports(treeUri)`.

Persist URI permission only when the provider grants it. A cancelled picker returns to `READY_TO_SAVE` and retains local files.

```kotlin
val coverDirectoryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
    if (uri == null) {
        coverViewModel.exportDirectoryCancelled()
    } else {
        runCatching {
            contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
        }
        coverViewModel.saveExports(uri)
    }
}
```

```kotlin
fun saveExports(treeUri: Uri) {
    val files = pendingExports ?: return
    viewModelScope.launch {
        _uiState.update { it.copy(status = CoverStatus.SAVING) }
        val result = withContext(Dispatchers.IO) {
            repository.saveExportPair(treeUri, files.pdf, files.docx, files.baseName)
        }
        _uiState.update {
            it.copy(
                status = if (result.docxUri != null) CoverStatus.COMPLETED else CoverStatus.READY_TO_SAVE,
                saveResult = result,
            )
        }
    }
}
```

- [ ] **Step 5: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest compileDebugAndroidTestKotlin
git add app/src/main/java/tw/daniel/epubword app/src/test app/src/androidTest
git commit -m "feat: export Android cover PDF and DOCX pair"
```

Expected: PASS.

---

### Task 10: Add conversion-completion handoff to cover creation

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/model/CoverHandoff.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/ConversionViewModel.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/ConverterScreen.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt`
- Create: `app/src/test/java/tw/daniel/epubword/ui/ConversionCoverHandoffTest.kt`

**Interfaces:**
- `CoverHandoff` contains copied source path, source type, actual page count, trim size, title, and author.
- Handoff source ownership transfers to cover session; conversion cleanup does not delete the copied file.

- [ ] **Step 1: Write failing handoff tests**

```kotlin
@Test fun handoffUsesActualConvertedPageCount() {
    val handoff = createCoverHandoff(
        source = stagedEpub,
        result = conversionResult(miniPageCount = 164),
        outputMode = OutputMode.SIGNATURE16,
    )
    assertEquals(164, handoff.pageCount)
    assertEquals(TrimSize(105.0, 148.0), handoff.trimSize)
    assertTrue(handoff.pageCountConfirmed)
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.ui.ConversionCoverHandoffTest'
```

Expected: compilation failure.

- [ ] **Step 3: Implement safe source copying**

`ConversionViewModel.requestCoverHandoff()` copies the staged source into a new cover-session directory, constructs the handoff, increments a one-shot request ID, and leaves the normal DOCX save workflow unchanged.

```kotlin
fun requestCoverHandoff() {
    val input = stagedInput ?: return
    val result = _uiState.value.result ?: return
    viewModelScope.launch {
        val copied = withContext(Dispatchers.IO) {
            repository.copyForCoverSession(input.localFile)
        }
        val handoff = CoverHandoff(
            sourcePath = copied.absolutePath,
            sourceType = input.kind.name.lowercase(),
            pageCount = result.miniPageCount,
            pageCountConfirmed = true,
            trimSize = _uiState.value.options.outputMode.coverTrimSize(),
            title = result.title,
            author = result.author,
        )
        _uiState.update {
            it.copy(
                coverHandoff = handoff,
                coverHandoffRequestId = it.coverHandoffRequestId + 1,
            )
        }
    }
}
```

- [ ] **Step 4: Add the completion action**

Show `製作獨立書封` only when conversion result exists. AppRoot consumes the handoff once, initializes `CoverViewModel`, and navigates directly to cover setup with actual page count already filled and confirmed.

```kotlin
AnimatedVisibility(visible = state.result != null && !state.isBusy) {
    OutlinedButton(onClick = onCreateCover, modifier = Modifier.fillMaxWidth()) {
        Text("製作獨立書封")
    }
}
```

```kotlin
LaunchedEffect(conversionState.coverHandoffRequestId) {
    val handoff = conversionState.coverHandoff ?: return@LaunchedEffect
    if (conversionState.coverHandoffRequestId > handledHandoffId) {
        handledHandoffId = conversionState.coverHandoffRequestId
        coverViewModel.openHandoff(handoff)
        routeState = routeState.navigate(AppRoute.COVER_SETUP, handoff)
        conversionViewModel.markCoverHandoffHandled(handledHandoffId)
    }
}
```

- [ ] **Step 5: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest
git add app/src/main/java/tw/daniel/epubword app/src/test
git commit -m "feat: hand completed conversions to Android cover tool"
```

Expected: all unit tests PASS.

---

### Task 11: Add Android acceptance tests and offline documentation

**Files:**
- Create: `app/src/androidTest/java/tw/daniel/epubword/cover/CoverWorkflowTest.kt`
- Create: `python-tests/cover/test_android_bridge_cover.py`
- Modify: `README.md`
- Modify: `BUILDING.md`
- Modify: `BUILD_STATUS.md`
- Modify: `scripts/verify_project.py`

**Interfaces:**
- Acceptance path: source → setup → template → local image → gesture patch → preview → 200 DPI local export.
- Project verifier confirms no `INTERNET` permission yet and canonical Python source configuration is active.

- [ ] **Step 1: Add bridge acceptance test**

```python
def test_android_cover_bridge_exports_both_formats(epub_fixture, tmp_path):
    project_json = android_bridge.cover_new_project_json(
        str(epub_fixture), json.dumps(valid_settings(tmp_path))
    )
    project_json = android_bridge.cover_apply_template_json(project_json, "minimal_text")
    result = json.loads(android_bridge.cover_export_json(
        project_json,
        str(tmp_path / "cover.pdf"),
        str(tmp_path / "cover.docx"),
        200,
    ))
    assert Path(result["pdf"]["path"]).is_file()
    assert Path(result["docx"]["path"]).is_file()
```

- [ ] **Step 2: Add Compose workflow test**

Use fake repository/gateway implementations so the test does not call Python. Assert route transitions, confirmation gate, editor actions, export DPI choice, and directory request event.

```kotlin
@Test
fun fullOfflineCoverWorkflowRequestsDirectoryAfterLocalExport() {
    val repository = FakeCoverDocumentRepository()
    val gateway = FakePythonCoverGateway()
    compose.setContent {
        TestAppRoot(repository = repository, gateway = gateway)
    }
    compose.onNodeWithText("封面工具").performClick()
    compose.onNodeWithText("選擇 EPUB、DOCX 或 PDF").performClick()
    repository.completeSourceSelection(sampleEpubUri)
    compose.onNodeWithText("我已確認正文頁數").performClick()
    compose.onNodeWithText("建立封面").performClick()
    compose.onNodeWithText("匯出").performClick()
    compose.onNodeWithText("200 DPI").performClick()
    compose.onNodeWithText("開始匯出").performClick()
    compose.waitUntil { gateway.exportCalls == 1 }
    assertEquals(1, repository.directoryRequestEvents)
    compose.onNodeWithText("封面編輯器").assertIsDisplayed()
}
```

- [ ] **Step 3: Run the complete Android gate**

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
gradle --no-daemon testDebugUnitTest assembleDebug
python3.13 scripts/verify_project.py
```

Expected: zero Python failures, zero Kotlin unit failures, debug APK created, project verification PASS.

- [ ] **Step 4: Verify manifest remains offline before search plan**

```bash
apkanalyzer manifest permissions app/build/outputs/apk/debug/app-debug.apk
```

Expected: no `android.permission.INTERNET` at this stage.

- [ ] **Step 5: Commit**

```bash
git add app/src/androidTest python-tests/cover README.md BUILDING.md BUILD_STATUS.md \
  scripts/verify_project.py
git commit -m "test: add Android cover workflow acceptance gate"
```
