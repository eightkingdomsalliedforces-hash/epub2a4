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

## Subpart B: Tasks 7–8

### Task 7: Implement touch-based cover canvas and selection overlays

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverEditorCanvas.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewport.kt`
- Create: `app/src/test/java/tw/daniel/epubword/cover/ui/CoverViewportTest.kt`
- Create: `app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverEditorCanvasTest.kt`

**Interfaces:**
- `CoverViewport` converts millimetres ↔ screen pixels and maintains pan/zoom.
- Canvas displays the rendered preview plus guide/selection overlays.
- Gestures emit one committed millimetre transform after gesture end.

- [ ] **Step 1: Write failing viewport math tests**

```kotlin
@Test fun mmRoundTripIsStable() {
    val viewport = CoverViewport(scalePxPerMm = 4.0, offsetPx = Offset(20f, 30f))
    val screen = viewport.mmToScreen(Offset(12.5f, 18.75f))
    val restored = viewport.screenToMm(screen)
    assertEquals(12.5f, restored.x, 0.0001f)
    assertEquals(18.75f, restored.y, 0.0001f)
}

@Test fun zoomIsClamped() {
    assertEquals(0.1f, CoverViewport(scalePxPerMm = 0.01).normalized().zoomFactor)
    assertEquals(8f, CoverViewport(scalePxPerMm = 1000.0).normalized().zoomFactor)
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.ui.CoverViewportTest'
```

Expected: compilation failure.

- [ ] **Step 3: Implement viewport and fit calculation**

```kotlin
data class CoverViewport(
    val scalePxPerMm: Double,
    val offsetPx: Offset = Offset.Zero,
) {
    fun mmToScreen(point: Offset): Offset = Offset(
        offsetPx.x + point.x * scalePxPerMm.toFloat(),
        offsetPx.y + point.y * scalePxPerMm.toFloat(),
    )

    fun screenToMm(point: Offset): Offset = Offset(
        (point.x - offsetPx.x) / scalePxPerMm.toFloat(),
        (point.y - offsetPx.y) / scalePxPerMm.toFloat(),
    )
}
```

Fit scale is `min(availableWidth/canvasWidthMm, availableHeight/canvasHeightMm) * 0.92`.

- [ ] **Step 4: Implement preview and overlay drawing**

Display preview bitmap with `Image`. Overlay a Compose `Canvas` drawing back/spine/front boundaries, bleed, safe zones, A4 boundaries, and selected element bounds. Guides are UI-only and not added to `CoverProject`.

```kotlin
@Composable
fun CoverEditorCanvas(
    bitmap: ImageBitmap,
    viewport: CoverViewport,
    guides: CoverGuides,
    selected: ElementTransform?,
    modifier: Modifier = Modifier,
) {
    Box(modifier.clipToBounds().background(Color.LightGray)) {
        Image(
            bitmap = bitmap,
            contentDescription = "封面預覽",
            modifier = Modifier.graphicsLayer {
                scaleX = viewport.scale
                scaleY = viewport.scale
                translationX = viewport.offsetPx.x
                translationY = viewport.offsetPx.y
            },
        )
        Canvas(Modifier.matchParentSize()) {
            withTransform({
                translate(viewport.offsetPx.x, viewport.offsetPx.y)
                scale(viewport.scale, viewport.scale)
            }) {
                guides.regionRects.forEach { drawRect(Color.Blue, it.topLeft, it.size, style = Stroke(1f)) }
                guides.safeRects.forEach { drawRect(Color.Green, it.topLeft, it.size, style = Stroke(1f)) }
                guides.a4Rects.forEach { drawRect(Color.Magenta, it.topLeft, it.size, style = Stroke(1f)) }
                selected?.let { drawRect(Color.Red, it.toOffset(), it.toSize(), style = Stroke(2f)) }
            }
        }
    }
}
```

- [ ] **Step 5: Implement gestures**

- one-finger drag on selected element moves it;
- two-finger gesture over selected element scales and rotates it;
- two-finger gesture outside selection pans/zooms viewport;
- long press selects the topmost element under the pointer;
- during gesture, update temporary overlay only;
- on gesture end, emit `ElementTransformPatch` in millimetres and request a debounced Python preview.

```kotlin
Modifier.pointerInput(selectedElementId, viewport) {
    awaitEachGesture {
        val first = awaitFirstDown()
        var pan = Offset.Zero
        var zoom = 1f
        var rotation = 0f
        do {
            val event = awaitPointerEvent()
            pan += event.calculatePan()
            zoom *= event.calculateZoom()
            rotation += event.calculateRotation()
            event.changes.forEach { if (it.positionChanged()) it.consume() }
        } while (event.changes.any { it.pressed })

        selectedElementId?.let { id ->
            onCommitTransform(
                ElementTransformPatch(
                    elementId = id,
                    deltaXMm = viewport.pxToMm(pan.x),
                    deltaYMm = viewport.pxToMm(pan.y),
                    scale = zoom.toDouble(),
                    rotationDeltaDeg = rotation.toDouble(),
                )
            )
        } ?: onCommitViewport(pan, zoom)
    }
}
```

- [ ] **Step 6: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest compileDebugAndroidTestKotlin
git add app/src/main/java/tw/daniel/epubword/cover/ui/CoverEditorCanvas.kt \
  app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewport.kt app/src/test app/src/androidTest
git commit -m "feat: add touch cover canvas with millimetre transforms"
```

Expected: tests PASS.

---

### Task 8: Add editor screen, element inspector, templates, and local images

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverEditorScreen.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/ElementInspectorSheet.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/LayersSheet.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverViewModel.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt`
- Create: `app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverEditorScreenTest.kt`

**Interfaces:**
- Toolbar: back, undo, redo, template, add image, add text, guides, export.
- Bottom sheets: layers and selected-element inspector.
- ViewModel methods: `selectElement`, `patchElement`, `addLocalImage`, `addText`, `removeElement`, `applyTemplate`, `undo`, `redo`.

- [ ] **Step 1: Add failing editor action tests**

```kotlin
@Test fun editorShowsCoreActions() {
    compose.setContent { CoverEditorScreen(state = sampleEditingState(), callbacks = noOps) }
    compose.onNodeWithContentDescription("復原").assertIsDisplayed()
    compose.onNodeWithContentDescription("重做").assertIsDisplayed()
    compose.onNodeWithText("加入圖片").assertIsDisplayed()
    compose.onNodeWithText("匯出").assertIsDisplayed()
}
```

- [ ] **Step 2: Run test compilation and verify failure**

```bash
gradle --no-daemon compileDebugAndroidTestKotlin
```

Expected: compilation failure.

- [ ] **Step 3: Add project history to ViewModel**

Store bounded before/after JSON snapshots:

```kotlin
private val undo = ArrayDeque<String>()
private val redo = ArrayDeque<String>()
private const val MAX_HISTORY = 50

private fun commitProject(next: CoverProject) {
    currentProject?.let { undo.addLast(CoverProjectJson.encode(it)) }
    while (undo.size > MAX_HISTORY) undo.removeFirst()
    redo.clear()
    currentProject = next
    schedulePreview()
}
```

- [ ] **Step 4: Build inspector controls**

Common: X/Y/W/H, rotation, opacity, delete.

Image: replace, contain/cover, crop dialog entry, flip, blur, brightness, dark overlay.

Text: content, font size, weight, color, alignment, line spacing, spine direction.

All numeric edits use explicit Apply or IME Done to avoid adding one undo entry per keystroke.

```kotlin
@Composable
fun ElementInspectorSheet(
    element: CoverElement,
    onApply: (ElementPatch) -> Unit,
    onDelete: () -> Unit,
) {
    var xText by remember(element.id) { mutableStateOf(element.transform.xMm.toString()) }
    var yText by remember(element.id) { mutableStateOf(element.transform.yMm.toString()) }
    Column(Modifier.navigationBarsPadding().padding(16.dp)) {
        OutlinedTextField(xText, { xText = it }, label = { Text("X（mm）") })
        OutlinedTextField(yText, { yText = it }, label = { Text("Y（mm）") })
        Button(onClick = {
            val x = xText.toDoubleOrNull() ?: return@Button
            val y = yText.toDoubleOrNull() ?: return@Button
            onApply(ElementPatch(transform = element.transform.copy(xMm = x, yMm = y)))
        }) { Text("套用") }
        TextButton(onClick = onDelete) { Text("刪除元素") }
        when (element.kind) {
            ElementKind.IMAGE -> ImageControls(element, onApply)
            ElementKind.TEXT -> TextControls(element, onApply)
            else -> Unit
        }
    }
}
```

- [ ] **Step 5: Add local and embedded image selection**

`MainActivity` adds an `OpenDocument` image launcher. The ViewModel copies selected content into session assets. Embedded EPUB images are shown from metadata and extracted through a new shared service/bridge helper already exposed by project creation; selecting one replaces/adds the image element without network.

```kotlin
val imageLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
    uri?.let(coverViewModel::importLocalImage)
}
```

```kotlin
fun importLocalImage(uri: Uri) {
    viewModelScope.launch {
        runCatching { repository.copyImageToAssets(uri, requireNotNull(workingFiles)) }
            .onSuccess { path -> replaceSelectedImage(path.absolutePath) }
            .onFailure { failure -> _uiState.update { it.copy(errorMessage = failure.message) } }
    }
}

fun selectEmbeddedImage(assetId: String) {
    viewModelScope.launch {
        runCatching { gateway.extractEmbeddedAsset(currentProjectJson, assetId) }
            .onSuccess(::replaceSelectedImage)
            .onFailure { failure -> _uiState.update { it.copy(errorMessage = failure.message) } }
    }
}
```

- [ ] **Step 6: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest compileDebugAndroidTestKotlin
git add app/src/main/java/tw/daniel/epubword/cover/ui \
  app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt app/src/androidTest
git commit -m "feat: add Android cover editor and element inspector"
```

Expected: tests PASS.

---
