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

## Subpart B: Tasks 3–4

### Task 3: Add a dedicated large-stack Python cover gateway

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/python/LargeStackPythonExecutor.kt`
- Create: `app/src/main/java/tw/daniel/epubword/python/PythonCoverGateway.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/python/PythonConversionGateway.kt`
- Create: `app/src/test/java/tw/daniel/epubword/python/LargeStackPythonExecutorTest.kt`
- Create: `app/src/test/java/tw/daniel/epubword/python/PythonCoverGatewayContractTest.kt`

**Interfaces:**
- Produces `LargeStackPythonExecutor.run(block)` with one worker thread and stack size `8L * 1024L * 1024L`.
- `PythonCoverGateway` methods: `inspectSource`, `newProject`, `applyTemplate`, `renderPreview`, `export`.
- Both gateways share the executor but maintain independent cancellation tokens.

- [ ] **Step 1: Write failing executor regression tests**

```kotlin
@Test
fun executorRunsOnDedicatedNamedThread() {
    LargeStackPythonExecutor().use { executor ->
        val name = executor.run { Thread.currentThread().name }
        assertTrue(name.startsWith("epub2a4-python-"))
    }
}

@Test
fun coverGatewayUsesExpectedBridgeFunctions() {
    assertEquals(
        listOf(
            "cover_inspect_source_json",
            "cover_new_project_json",
            "cover_apply_template_json",
            "cover_render_preview_json",
            "cover_export_json",
        ),
        PythonCoverGateway.BRIDGE_FUNCTIONS,
    )
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.python.*Cover*' \
  --tests 'tw.daniel.epubword.python.LargeStackPythonExecutorTest'
```

Expected: compilation failure.

- [ ] **Step 3: Extract the proven large-stack execution code**

```kotlin
class LargeStackPythonExecutor : AutoCloseable {
    private val executor = Executors.newSingleThreadExecutor { runnable ->
        Thread(null, runnable, "epub2a4-python-${THREAD_ID.incrementAndGet()}", STACK_BYTES)
    }

    fun <T> run(block: () -> T): T = executor.submit(Callable(block)).get()

    override fun close() {
        executor.shutdownNow()
    }

    private companion object {
        const val STACK_BYTES = 8L * 1024L * 1024L
        val THREAD_ID = AtomicLong(0)
    }
}
```

Refactor `PythonConversionGateway` to receive or own this class without changing `ProgressProxy.progressCallback` naming or reintroducing recursion.

- [ ] **Step 4: Implement cover bridge calls**

```kotlin
class PythonCoverGateway(context: Context) : AutoCloseable {
    private val executor = LargeStackPythonExecutor()
    private val module by lazy {
        if (!Python.isStarted()) Python.start(AndroidPlatform(context.applicationContext))
        Python.getInstance().getModule("android_bridge")
    }

    fun inspectSource(source: File): JSONObject = executor.run {
        JSONObject(module.callAttr("cover_inspect_source_json", source.absolutePath).toString())
    }

    fun newProject(source: File, settings: JSONObject): String = executor.run {
        module.callAttr("cover_new_project_json", source.absolutePath, settings.toString()).toString()
    }

    fun applyTemplate(projectJson: String, templateId: String): String = executor.run {
        module.callAttr("cover_apply_template_json", projectJson, templateId).toString()
    }
}
```

Add render/export methods with explicit output paths and parse returned JSON.

- [ ] **Step 5: Run gateway and existing conversion tests**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.python.*'
```

Expected: PASS, including the progress callback recursion regression test.

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/tw/daniel/epubword/python app/src/test/java/tw/daniel/epubword/python
git commit -m "refactor: share large-stack Python executor with cover gateway"
```

---

### Task 4: Stage cover inputs, assets, previews, and paired outputs

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/data/CoverDocumentRepository.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/data/CoverWorkingFiles.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/data/DocumentRepository.kt`
- Create: `app/src/test/java/tw/daniel/epubword/cover/data/CoverDocumentRepositoryTest.kt`

**Interfaces:**
- Produces `stageSource(uri) -> StagedCoverSource` for EPUB/DOCX/PDF.
- Produces `stageLocalImage(uri) -> File`.
- Produces `createPreviewFile()`, `createPdfFile(title)`, `createDocxFile(title)`.
- Produces `saveExportPair(pdf, docx, treeUri) -> SavedCoverFiles`.

- [ ] **Step 1: Write failing filename and MIME tests**

```kotlin
@Test fun acceptsOnlySupportedCoverInputs() {
    assertEquals(CoverInputKind.EPUB, kindFor("book.epub", "application/epub+zip"))
    assertEquals(CoverInputKind.DOCX, kindFor("book.docx", DOCX_MIME))
    assertEquals(CoverInputKind.PDF, kindFor("book.pdf", "application/pdf"))
    assertFailsWith<IllegalArgumentException> { kindFor("book.txt", "text/plain") }
}

@Test fun sanitizesIndependentExportNames() {
    assertEquals("測試書_完整書封.pdf", coverExportName("測試書/", "pdf"))
    assertEquals("測試書_完整書封.docx", coverExportName("測試書/", "docx"))
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.data.CoverDocumentRepositoryTest'
```

Expected: compilation failure.

- [ ] **Step 3: Implement isolated working directories**

Use:

```text
cacheDir/cover/<session-id>/source/
cacheDir/cover/<session-id>/assets/
cacheDir/cover/<session-id>/preview/
cacheDir/cover/<session-id>/export/
```

Copy only through `ContentResolver.openInputStream`. Enforce source maximum `500 MiB`, image maximum `50 MiB`, and reject zero-byte files. Delete a session recursively when its ViewModel is cleared unless an export retry is pending.

```kotlin
private const val MAX_SOURCE_BYTES = 500L * 1024L * 1024L
private const val MAX_IMAGE_BYTES = 50L * 1024L * 1024L

data class CoverWorkingFiles(
    val root: File,
    val sourceDir: File,
    val assetsDir: File,
    val previewDir: File,
    val exportDir: File,
    val sourceFile: File,
)

fun createSession(): CoverWorkingFiles {
    val root = File(context.cacheDir, "cover/${UUID.randomUUID()}")
    val source = File(root, "source").apply(File::mkdirs)
    val assets = File(root, "assets").apply(File::mkdirs)
    val preview = File(root, "preview").apply(File::mkdirs)
    val export = File(root, "export").apply(File::mkdirs)
    return CoverWorkingFiles(root, source, assets, preview, export, File(source, "pending"))
}

fun copyUri(uri: Uri, destination: File, maxBytes: Long): Long {
    destination.parentFile?.mkdirs()
    val temporary = File(destination.parentFile, destination.name + ".part")
    var copied = 0L
    context.contentResolver.openInputStream(uri).use { input ->
        requireNotNull(input) { "無法開啟所選檔案。" }
        temporary.outputStream().buffered(1024 * 1024).use { output ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                copied += count
                require(copied <= maxBytes) { "檔案超過允許大小。" }
                output.write(buffer, 0, count)
            }
        }
    }
    require(copied > 0) { "檔案內容是空的。" }
    check(temporary.renameTo(destination)) { "無法完成工作檔案寫入。" }
    return copied
}

fun clearSession(files: CoverWorkingFiles, keepForRetry: Boolean) {
    if (!keepForRetry) files.root.deleteRecursively()
}
```

- [ ] **Step 4: Implement two-file SAF directory save**

Use `ActivityResultContracts.OpenDocumentTree`. Convert tree URI to its root document URI and call `DocumentsContract.createDocument` for:

```text
application/pdf               <title>_完整書封.pdf
application/vnd.openxmlformats-officedocument.wordprocessingml.document
                              <title>_完整書封.docx
```

Copy with 1 MiB buffers. If PDF saves but DOCX fails, return a partial result naming the saved PDF and keep local outputs for retry; do not claim complete success.

```kotlin
fun saveExportPair(treeUri: Uri, pdf: File, docx: File, title: String): SavedCoverFiles {
    val rootDocumentId = DocumentsContract.getTreeDocumentId(treeUri)
    val rootUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, rootDocumentId)
    val pdfUri = createAndCopy(
        rootUri,
        "application/pdf",
        coverExportName(title, "pdf"),
        pdf,
    )
    return try {
        val docxUri = createAndCopy(
            rootUri,
            DOCX_MIME,
            coverExportName(title, "docx"),
            docx,
        )
        SavedCoverFiles(pdfUri = pdfUri, docxUri = docxUri)
    } catch (failure: Throwable) {
        SavedCoverFiles(
            pdfUri = pdfUri,
            docxUri = null,
            errorMessage = failure.message ?: "DOCX 儲存失敗。",
        )
    }
}

private fun createAndCopy(parent: Uri, mime: String, name: String, source: File): Uri {
    val destination = requireNotNull(
        DocumentsContract.createDocument(context.contentResolver, parent, mime, name)
    ) { "無法建立 $name。" }
    context.contentResolver.openOutputStream(destination, "w").use { output ->
        requireNotNull(output) { "無法寫入 $name。" }
        source.inputStream().buffered(1024 * 1024).use { input -> input.copyTo(output, 1024 * 1024) }
    }
    return destination
}
```

- [ ] **Step 5: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.data.CoverDocumentRepositoryTest'
git add app/src/main/java/tw/daniel/epubword/cover/data \
  app/src/main/java/tw/daniel/epubword/data/DocumentRepository.kt app/src/test
git commit -m "feat: add Android cover document repository"
```

Expected: PASS.

---
