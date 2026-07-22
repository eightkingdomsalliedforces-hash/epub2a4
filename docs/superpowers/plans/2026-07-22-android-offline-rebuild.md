# Android Offline Converter Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible arm64 Android application which converts EPUB and DOCX files entirely offline into the same DOCX print layouts as desktop v0.5.0.

**Architecture:** A Jetpack Compose Android shell stages files through the Storage Access Framework and invokes the proven Python conversion core through Chaquopy. A small Python bridge validates JSON options, adapts progress/cancellation callbacks, and returns a JSON result; the Kotlin ViewModel owns lifecycle, progress, temporary files, and save operations.

**Tech Stack:** Kotlin 2.3.10, Jetpack Compose, Android API 24–36, AGP 8.13.2, Gradle 8.13, Chaquopy 17.0.0, Python 3.13, python-docx, lxml, Pillow, BeautifulSoup.

## Global Constraints

- Operate fully offline after installation; do not declare INTERNET or broad storage permissions.
- Support only `arm64-v8a`, Android 7.0/API 24 or newer.
- Accept EPUB and DOCX through SAF and emit editable DOCX through SAF.
- Preserve desktop v0.5.0 conversion behavior and paragraph boundaries.
- EPUB supports A4 four-up, A6 16-page signatures, A5 single-page, and 4×6 single-page.
- DOCX supports A5 and 4×6 reflow only.
- Conversion runs off the main thread and exposes progress, cancellation, warnings, and result statistics.

---

### Task 1: Reconstruct the Python Android bridge

**Files:**
- Create: `app/src/main/python/android_bridge.py`
- Copy: `app/src/main/python/epub_a4_word/*.py`
- Test: `python-tests/test_android_bridge.py`

**Interfaces:**
- Consumes: desktop `convert_input(input_path, output_path, settings, progress)`.
- Produces: `convert_file(...) -> dict`, `convert_file_json(...) -> str`, `probe() -> dict`.

- [ ] Write bridge tests for option validation, progress forwarding, cancellation, and JSON-safe results.
- [ ] Run tests and verify they fail because `android_bridge` is absent.
- [ ] Implement the minimal bridge and copy the desktop core without GUI entry points.
- [ ] Run all Python tests and compile all Python sources.

### Task 2: Create a reproducible Android/Chaquopy build

**Files:**
- Create: `settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`
- Create: `app/build.gradle.kts`, `app/proguard-rules.pro`, `app/src/main/AndroidManifest.xml`
- Create: `.github/workflows/android.yml`

**Interfaces:**
- Consumes: Python source and Android-compatible PyPI packages.
- Produces: an arm64 debug APK build configuration and CI artifact workflow.

- [ ] Configure API 24–36, arm64 only, Compose, Chaquopy Python 3.13, and pinned Python dependencies.
- [ ] Add a Gradle CI workflow which builds and uploads the debug APK without requiring a committed wrapper.
- [ ] Add static checks for forbidden permissions and required ABI/version settings.

### Task 3: Implement file staging and the Python gateway

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/data/DocumentRepository.kt`
- Create: `app/src/main/java/tw/daniel/epubword/python/PythonConversionGateway.kt`
- Create: `app/src/main/java/tw/daniel/epubword/model/ConversionModels.kt`
- Test: `app/src/test/java/tw/daniel/epubword/model/ConversionModelsTest.kt`

**Interfaces:**
- Consumes: SAF content URIs, Kotlin `ConversionOptions`, Python bridge.
- Produces: staged local files, `ConversionResult`, and progress/cancellation callbacks.

- [ ] Define input/mode constraints and deterministic JSON option encoding.
- [ ] Stage selected files into app cache and copy completed outputs to a user-selected URI.
- [ ] Invoke `android_bridge.convert_file_json` and map failures to user-facing categories.

### Task 4: Implement lifecycle-safe conversion state

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/ui/ConversionViewModel.kt`
- Test: `app/src/test/java/tw/daniel/epubword/ui/ConversionReducerTest.kt`

**Interfaces:**
- Consumes: repository, gateway, user intents.
- Produces: immutable `StateFlow<ConversionUiState>`.

- [ ] Implement selection, mode normalization, conversion, cancellation, save, and temporary-file cleanup.
- [ ] Keep all filesystem and Python work on `Dispatchers.IO`.
- [ ] Ensure save-dialog requests are single-shot and retryable.

### Task 5: Build the Compose user interface

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/MainActivity.kt`
- Create: `app/src/main/java/tw/daniel/epubword/ui/ConverterScreen.kt`
- Create: `app/src/main/java/tw/daniel/epubword/ui/theme/Theme.kt`
- Create: `app/src/main/res/values/strings.xml`, `themes.xml`

**Interfaces:**
- Consumes: `ConversionUiState` and ViewModel intent callbacks.
- Produces: four-step Chinese UI using OpenDocument/CreateDocument contracts.

- [ ] Implement input selection and context-sensitive output modes.
- [ ] Implement margins, font/size, page number, and cut-guide controls.
- [ ] Show progress, cancellation, warnings, statistics, and save result.

### Task 6: Verify and package

**Files:**
- Create: `README.md`, `BUILDING.md`, `scripts/verify_project.py`
- Output: `EPUB_Word_Android_離線版_原始碼.zip`
- Output when build tooling is available: `EPUB_Word_Android_離線版-debug.apk`

**Interfaces:**
- Consumes: the complete project and test fixture documents.
- Produces: a reproducible source archive, test evidence, and APK if the environment can resolve Android build tools.

- [ ] Run desktop and bridge Python tests, source compilation, and project static verification.
- [ ] Run Gradle unit tests and `assembleDebug` when Android/Gradle dependencies are available.
- [ ] Inspect APK ABI and permissions when an APK is produced.
- [ ] Package source and state exactly which runtime verifications were and were not possible.
