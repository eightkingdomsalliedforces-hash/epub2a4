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

## Subpart A: Tasks 5–6

### Task 5: Implement CoverViewModel state and source/setup workflow

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewModel.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverUiState.kt`
- Create: `app/src/test/java/tw/daniel/epubword/cover/ui/CoverViewModelTest.kt`

**Interfaces:**
- Statuses: `IDLE`, `STAGING`, `INSPECTING`, `SETUP`, `CREATING`, `EDITING`, `RENDERING`, `EXPORTING`, `READY_TO_SAVE`, `SAVING`, `ERROR`.
- Methods: `selectSource`, `setTrimPreset`, `setPageCount`, `confirmPageCount`, `setPaperPreset`, `setCaliper`, `setManualSpine`, `setBleed`, `setImageMode`, `createProject`.
- State exposes computed sheet count, automatic spine width, effective spine width, and whether create/export is allowed.

- [ ] **Step 1: Write failing state transition tests**

```kotlin
@Test fun estimatedPageCountRequiresConfirmation() = runTest {
    val vm = createViewModel(metadataPageCount = null, estimatedPageCount = 160)
    vm.selectSource(fakeUri)
    advanceUntilIdle()
    assertEquals(CoverStatus.SETUP, vm.uiState.value.status)
    assertFalse(vm.uiState.value.pageCountConfirmed)
    assertFalse(vm.uiState.value.canCreateProject)
}

@Test fun spineUsesCeilingSheetCount() {
    val state = CoverUiState(pageCount = 161, paperCaliperMm = 0.10)
    assertEquals(81, state.sheetCount)
    assertEquals(8.1, state.autoSpineWidthMm, 0.0001)
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.ui.CoverViewModelTest'
```

Expected: compilation failure.

- [ ] **Step 3: Implement pure setup state calculations**

```kotlin
val sheetCount: Int get() = (pageCount + 1) / 2
val autoSpineWidthMm: Double get() = sheetCount * paperCaliperMm
val effectiveSpineWidthMm: Double get() = manualSpineWidthMm ?: autoSpineWidthMm
val canCreateProject: Boolean get() =
    stagedSource != null && pageCount > 0 && pageCountConfirmed && !isBusy
```

Paper presets:

```kotlin
enum class PaperPreset(val gsm: Int, val caliperMm: Double) {
    GSM_70(70, 0.09), GSM_80(80, 0.10), GSM_100(100, 0.12), GSM_120(120, 0.14)
}
```

- [ ] **Step 4: Implement asynchronous source inspection**

Inject repository and gateway for tests. Stage on `Dispatchers.IO`; gateway itself moves Python work to the large-stack executor. Preserve warnings and mark fixed PDF/DOCX page counts confirmed only after the user checks the confirmation box; never silently confirm metadata values.

```kotlin
fun selectSource(uri: Uri) {
    if (uiState.value.isBusy) return
    viewModelScope.launch {
        _uiState.update { it.copy(status = CoverStatus.STAGING, errorMessage = null) }
        runCatching {
            withContext(Dispatchers.IO) { repository.stageSource(uri) }
        }.mapCatching { staged ->
            staged to gateway.inspectSource(staged.sourceFile)
        }.onSuccess { (staged, inspection) ->
            workingFiles = staged
            _uiState.update {
                it.copy(
                    status = CoverStatus.SETUP,
                    sourceName = staged.displayName,
                    metadata = inspection.metadata,
                    pageCount = inspection.pageCount,
                    pageCountEstimated = inspection.pageCountEstimated,
                    pageCountConfirmed = false,
                    warnings = inspection.warnings,
                )
            }
        }.onFailure { failure ->
            _uiState.update {
                it.copy(status = CoverStatus.ERROR, errorMessage = failure.message ?: "無法讀取來源文件。")
            }
        }
    }
}
```

- [ ] **Step 5: Implement project creation**

Build settings JSON with working directory, trim, page count, caliper, spine override, bleed, overlap `5.0`, and image mode. Call `newProject`, then `applyTemplate` using the selected template. Move to `EDITING` only after a preview succeeds.

```kotlin
fun createProject() {
    val state = _uiState.value
    val files = workingFiles ?: return
    if (!state.pageCountConfirmed || state.pageCount == null) {
        _uiState.update { it.copy(errorMessage = "請確認正文頁數。") }
        return
    }
    viewModelScope.launch {
        _uiState.update { it.copy(status = CoverStatus.CREATING, errorMessage = null) }
        runCatching {
            val settings = JSONObject()
                .put("working_dir", files.root.absolutePath)
                .put("trim_width_mm", state.trimSize.widthMm)
                .put("trim_height_mm", state.trimSize.heightMm)
                .put("page_count", state.pageCount)
                .put("paper_caliper_mm", state.paperCaliperMm)
                .put("manual_spine_width_mm", state.manualSpineWidthMm ?: JSONObject.NULL)
                .put("bleed_mm", state.bleedMm)
                .put("overlap_mm", 5.0)
                .put("image_mode", state.imageMode.wire)
                .toString()
            val created = gateway.newProject(files.sourceFile, settings)
            val templated = gateway.applyTemplate(created, state.templateId)
            val preview = gateway.renderPreview(templated, files.nextPreviewFile(), 1600)
            Triple(CoverProjectJson.decode(templated), templated, preview)
        }.onSuccess { (project, json, preview) ->
            currentProject = project
            currentProjectJson = json
            _uiState.update {
                it.copy(status = CoverStatus.EDITING, project = project, previewFile = preview.path)
            }
        }.onFailure { failure ->
            _uiState.update { it.copy(status = CoverStatus.ERROR, errorMessage = failure.message) }
        }
    }
}
```

- [ ] **Step 6: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.ui.CoverViewModelTest'
git add app/src/main/java/tw/daniel/epubword/cover/ui app/src/test
git commit -m "feat: add Android cover setup state machine"
```

Expected: PASS.

---

### Task 6: Build the Compose cover setup screen

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverSetupScreen.kt`
- Create: `app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverSetupScreenTest.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt`

**Interfaces:**
- Screen displays source metadata and all required physical settings.
- Emits `onChooseSource`, `onCreateProject`, and setting callbacks.
- Supports portrait phone scrolling and wider two-column layout.

- [ ] **Step 1: Write failing Compose tests**

```kotlin
@Test fun estimatedPagesShowWarningAndConfirmation() {
    compose.setContent {
        CoverSetupScreen(
            state = sampleSetupState(pageCountEstimated = true, pageCountConfirmed = false),
            onChooseSource = {}, onCreateProject = {}, callbacks = noOpCallbacks,
        )
    }
    compose.onNodeWithText("頁數為估算值").assertIsDisplayed()
    compose.onNodeWithText("我已確認正文頁數").assertIsNotChecked()
    compose.onNodeWithText("建立封面").assertIsNotEnabled()
}

@Test fun showsAutomaticAndEffectiveSpineWidth() {
    compose.setContent { CoverSetupScreen(state = sampleSetupState(), callbacks = noOpCallbacks) }
    compose.onNodeWithText("自動書脊：8.0 mm").assertIsDisplayed()
}
```

- [ ] **Step 2: Run test compilation and verify failure**

```bash
gradle --no-daemon compileDebugAndroidTestKotlin
```

Expected: compilation failure because `CoverSetupScreen` does not exist.

- [ ] **Step 3: Implement setup cards**

Cards:

1. source and extracted metadata;
2. trim size and page count;
3. paper preset/custom caliper and spine override;
4. bleed, image mode, template;
5. create project status.

Use `OutlinedTextField` with decimal keyboard for caliper/spine and integer keyboard for page count. Parse with `toDoubleOrNull`; preserve last valid model value and show field-specific errors.

```kotlin
@Composable
private fun PageCountCard(state: CoverUiState, callbacks: CoverSetupCallbacks) {
    StepCard("正文頁數") {
        OutlinedTextField(
            value = state.pageCountText,
            onValueChange = callbacks.onPageCountText,
            label = { Text("頁數") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            isError = state.pageCountError != null,
            supportingText = { state.pageCountError?.let { Text(it) } },
            modifier = Modifier.fillMaxWidth(),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(
                checked = state.pageCountConfirmed,
                onCheckedChange = callbacks.onConfirmPageCount,
            )
            Text("我已確認正文頁數")
        }
        if (state.pageCountEstimated) Text("頁數為估算值", color = MaterialTheme.colorScheme.error)
    }
}

fun parsePositiveDouble(text: String, field: String): Result<Double> = runCatching {
    val value = text.toDoubleOrNull() ?: error("$field 必須是數字。")
    require(value > 0) { "$field 必須大於 0。" }
    value
}
```

- [ ] **Step 4: Add responsive layout**

Use `BoxWithConstraints`: under `700.dp`, one vertical column; at or above `700.dp`, two balanced columns. Every primary action has at least 48 dp touch height.

```kotlin
@Composable
fun CoverSetupScreen(state: CoverUiState, callbacks: CoverSetupCallbacks) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val cards: List<@Composable () -> Unit> = listOf(
            { SourceCard(state, callbacks) },
            { TrimAndPageCard(state, callbacks) },
            { PaperAndSpineCard(state, callbacks) },
            { AppearanceCard(state, callbacks) },
            { CreateProjectCard(state, callbacks) },
        )
        if (maxWidth < 700.dp) {
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(cards.size) { cards[it]() }
            }
        } else {
            Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    cards.filterIndexed { index, _ -> index % 2 == 0 }.forEach { it() }
                }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    cards.filterIndexed { index, _ -> index % 2 == 1 }.forEach { it() }
                }
            }
        }
    }
}
```

- [ ] **Step 5: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest compileDebugAndroidTestKotlin
git add app/src/main/java/tw/daniel/epubword/cover/ui/CoverSetupScreen.kt \
  app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt app/src/androidTest
git commit -m "feat: add Android cover setup screen"
```

Expected: unit tests PASS and Android test sources compile.

---
