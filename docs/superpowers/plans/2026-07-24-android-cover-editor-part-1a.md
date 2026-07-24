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

## Subpart A: Tasks 1–2

### Task 1: Add app-level routes without regressing the converter

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/ui/AppRoot.kt`
- Create: `app/src/main/java/tw/daniel/epubword/ui/HomeScreen.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/MainActivity.kt`
- Create: `app/src/test/java/tw/daniel/epubword/ui/AppRouteTest.kt`
- Create: `app/src/androidTest/java/tw/daniel/epubword/ui/AppRootTest.kt`

**Interfaces:**
- Produces `enum class AppRoute { HOME, CONVERTER, COVER_SETUP, COVER_EDITOR }`.
- `AppRoot` owns route state and receives file/directory launcher callbacks from `MainActivity`.
- Existing `ConverterScreen` remains reusable and unchanged in behavior.

- [ ] **Step 1: Write failing route transition tests**

```kotlin
class AppRouteStateTest {
    @Test
    fun startsAtHome() {
        assertEquals(AppRoute.HOME, AppRouteState().route)
    }

    @Test
    fun openCoverStartsAtSetup() {
        val state = AppRouteState().navigate(AppRoute.COVER_SETUP)
        assertEquals(AppRoute.COVER_SETUP, state.route)
    }
}
```

Compose test:

```kotlin
@get:Rule val compose = createComposeRule()

@Test fun homeOffersConverterAndCoverTools() {
    compose.setContent { EpubWordTheme { HomeScreen({}, {}) } }
    compose.onNodeWithText("轉換 EPUB／Word").assertIsDisplayed()
    compose.onNodeWithText("封面工具").assertIsDisplayed()
}
```

- [ ] **Step 2: Run tests and verify missing symbols fail**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.ui.AppRouteStateTest'
```

Expected: Kotlin compilation fails because `AppRoute` and `AppRouteState` do not exist.

- [ ] **Step 3: Implement immutable route state**

```kotlin
enum class AppRoute { HOME, CONVERTER, COVER_SETUP, COVER_EDITOR }

data class AppRouteState(
    val route: AppRoute = AppRoute.HOME,
    val coverHandoff: CoverHandoff? = null,
) {
    fun navigate(next: AppRoute, handoff: CoverHandoff? = coverHandoff): AppRouteState =
        copy(route = next, coverHandoff = handoff)
}
```

`AppRoot` uses `rememberSaveable` for the route name only. Cover project state lives in `CoverViewModel`, not in `rememberSaveable`.

- [ ] **Step 4: Refactor MainActivity to host launchers and AppRoot**

Keep the existing input and DOCX output launchers. Add callbacks into `AppRoot`; do not put conversion or cover business logic in `MainActivity`.

`HomeScreen` uses two full-width cards/buttons and displays `本機排版；搜尋封面需由使用者主動啟用` only after the search plan adds network support.

```kotlin
// MainActivity.kt
setContent {
    EpubWordTheme {
        AppRoot(
            onChooseConversionSource = { inputLauncher.launch(INPUT_MIME_TYPES) },
            onSaveConvertedDocx = { name -> convertedOutputLauncher.launch(name) },
            onChooseCoverSource = { coverSourceLauncher.launch(COVER_INPUT_MIME_TYPES) },
            onChooseCoverImage = { imageLauncher.launch(arrayOf("image/*")) },
            onChooseCoverDirectory = { coverDirectoryLauncher.launch(null) },
        )
    }
}
```

```kotlin
@Composable
fun HomeScreen(onOpenConverter: () -> Unit, onOpenCover: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Button(onClick = onOpenConverter, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
            Text("轉換 EPUB／Word")
        }
        OutlinedButton(onClick = onOpenCover, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
            Text("封面工具")
        }
    }
}
```

- [ ] **Step 5: Run existing and new UI tests**

```bash
gradle --no-daemon testDebugUnitTest
```

Expected: all existing converter tests and route tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/tw/daniel/epubword app/src/test app/src/androidTest
git commit -m "feat: add Android app navigation for cover workflow"
```

---

### Task 2: Mirror CoverProject schema v1 in Kotlin

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/model/CoverModels.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/model/CoverProjectJson.kt`
- Create: `app/src/test/java/tw/daniel/epubword/cover/model/CoverProjectJsonTest.kt`
- Add fixture: `app/src/test/resources/cover-project-v1.json`

**Interfaces:**
- Produces Kotlin models matching Python snake_case JSON exactly.
- Produces `CoverProjectJson.decode(text: String): CoverProject` and `encode(project): String`.
- Unknown schema version and unknown enum values fail with `CoverProjectFormatException`.

- [ ] **Step 1: Add a failing Python/Kotlin shared-fixture test**

```kotlin
@Test
fun decodesSchemaV1Fixture() {
    val text = javaClass.getResource("/cover-project-v1.json")!!.readText()
    val project = CoverProjectJson.decode(text)
    assertEquals(1, project.schemaVersion)
    assertEquals("範例書", project.metadata.title)
    assertEquals(ImageMode.FRONT_ONLY, project.imageMode)
    assertEquals(160, project.pageCount)
}

@Test
fun encodeDecodePreservesMillimetres() {
    val project = sampleProject()
    val restored = CoverProjectJson.decode(CoverProjectJson.encode(project))
    assertEquals(12.75, restored.elements.first().transform.xMm, 0.000001)
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.model.CoverProjectJsonTest'
```

Expected: compilation failure because cover models do not exist.

- [ ] **Step 3: Define exact Kotlin data classes**

```kotlin
enum class ImageMode(val wire: String) { FRONT_ONLY("front_only"), FULL_SPREAD("full_spread") }
enum class ElementKind(val wire: String) { IMAGE("image"), TEXT("text"), SHAPE("shape"), BARCODE_PLACEHOLDER("barcode_placeholder"), GUIDE("guide") }
enum class CoverRegion(val wire: String) { BACK("back"), SPINE("spine"), FRONT("front"), SPREAD("spread") }

data class TrimSize(val widthMm: Double, val heightMm: Double)
data class ElementTransform(
    val xMm: Double,
    val yMm: Double,
    val widthMm: Double,
    val heightMm: Double,
    val rotationDeg: Double = 0.0,
)
data class CoverElement(
    val id: String,
    val kind: ElementKind,
    val region: CoverRegion,
    val transform: ElementTransform,
    val zIndex: Int,
    val opacity: Double,
    val content: JSONObject,
)
data class CoverProject(
    val schemaVersion: Int,
    val sourceFile: String,
    val sourceType: String,
    val metadata: CoverMetadata,
    val trimSize: TrimSize,
    val pageCount: Int,
    val paperCaliperMm: Double,
    val manualSpineWidthMm: Double?,
    val bleedMm: Double,
    val overlapMm: Double,
    val imageMode: ImageMode,
    val background: JSONObject,
    val elements: List<CoverElement>,
    val exportSettings: CoverExportSettings,
)
```

Use the already available `org.json` dependency; do not add a second serialization library.

- [ ] **Step 4: Implement strict parsing helpers**

Every required property uses `get*`, optional properties use explicit `has/isNull`, and enums map through their `wire` values. Reject `schema_version != 1`, duplicate element IDs, non-positive dimensions, invalid opacity, and invalid page count before exposing the project to UI.

```kotlin
object CoverProjectJson {
    fun decode(text: String): CoverProject {
        val root = JSONObject(text)
        val schemaVersion = root.getInt("schema_version")
        if (schemaVersion != 1) throw CoverProjectFormatException("不支援的封面專案版本：$schemaVersion")
        val elements = root.getJSONArray("elements").let { array ->
            buildList {
                for (index in 0 until array.length()) add(decodeElement(array.getJSONObject(index)))
            }
        }
        if (elements.map { it.id }.toSet().size != elements.size) {
            throw CoverProjectFormatException("封面元素 ID 不可重複。")
        }
        val pageCount = root.getInt("page_count")
        if (pageCount <= 0) throw CoverProjectFormatException("頁數必須大於 0。")
        return CoverProject(
            schemaVersion = schemaVersion,
            sourceFile = root.getString("source_file"),
            sourceType = root.getString("source_type"),
            metadata = decodeMetadata(root.getJSONObject("metadata")),
            trimSize = decodeTrim(root.getJSONObject("trim_size_mm")),
            pageCount = pageCount,
            paperCaliperMm = root.getDouble("paper_caliper_mm"),
            manualSpineWidthMm = root.optionalDouble("manual_spine_width_mm"),
            bleedMm = root.getDouble("bleed_mm"),
            overlapMm = root.getDouble("overlap_mm"),
            imageMode = ImageMode.entries.singleOrNull { it.wire == root.getString("image_mode") }
                ?: throw CoverProjectFormatException("未知圖片模式。"),
            background = root.getJSONObject("background"),
            elements = elements,
            exportSettings = decodeExport(root.getJSONObject("export_settings")),
        ).also(::validate)
    }

    private fun JSONObject.optionalDouble(key: String): Double? =
        if (!has(key) || isNull(key)) null else getDouble(key)

    private fun validate(project: CoverProject) {
        require(project.trimSize.widthMm > 0 && project.trimSize.heightMm > 0)
        project.elements.forEach {
            if (it.transform.widthMm <= 0 || it.transform.heightMm <= 0) {
                throw CoverProjectFormatException("元素尺寸必須大於 0：${it.id}")
            }
            if (it.opacity !in 0.0..1.0) {
                throw CoverProjectFormatException("元素透明度必須介於 0 與 1：${it.id}")
            }
        }
    }
}
```

- [ ] **Step 5: Generate the fixture from Python and run both sides**

```bash
mkdir -p app/src/test/resources
cp python-tests/fixtures/cover/golden-project.json \
  app/src/test/resources/cover-project-v1.json
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.model.CoverProjectJsonTest'
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/src/main/java/tw/daniel/epubword/cover/model \
  app/src/test/java/tw/daniel/epubword/cover/model app/src/test/resources
git commit -m "feat: add Android cover project schema models"
```

---
