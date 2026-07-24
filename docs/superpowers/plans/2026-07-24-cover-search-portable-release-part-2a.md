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

## Subpart A: Tasks 5–6

### Task 5: Add Android network permission and encrypted credential store

**Files:**
- Modify: `app/src/main/AndroidManifest.xml`
- Modify: `app/build.gradle.kts`
- Create: `app/src/main/java/tw/daniel/epubword/cover/search/ApiCredentialStore.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/search/CredentialCipher.kt`
- Create: `app/src/test/java/tw/daniel/epubword/cover/search/ApiCredentialStoreTest.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/ui/ConverterScreen.kt`

**Interfaces:**
- Produces `SearchCredential(apiKey, searchEngineId)`.
- Store methods: `load()`, `save(credential)`, `clear()`.
- Android Keystore alias: `epub2a4-cover-search-v1`.

- [ ] **Step 1: Write failing store behavior tests with fake cipher**

```kotlin
@Test fun saveDoesNotStorePlaintext() {
    val prefs = inMemoryPreferences()
    val store = ApiCredentialStore(prefs, FakeCredentialCipher())
    store.save(SearchCredential("secret-api-key", "engine-id"))
    assertFalse(prefs.all.values.any { it.toString().contains("secret-api-key") })
    assertEquals(SearchCredential("secret-api-key", "engine-id"), store.load())
}

@Test fun clearRemovesBothValues() {
    val store = createStoreWithCredential()
    store.clear()
    assertNull(store.load())
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.search.ApiCredentialStoreTest'
```

Expected: compilation failure.

- [ ] **Step 3: Add permission and image-loader dependencies**

Manifest:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

Gradle:

```kotlin
implementation("io.coil-kt.coil3:coil-compose:3.5.0")
implementation("io.coil-kt.coil3:coil-network-okhttp:3.5.0")
```

Remove `完全離線` claims from runtime UI. Replace with `文件本機處理 · 僅搜尋時連線`.

- [ ] **Step 4: Implement API 24-compatible Keystore AES-GCM**

Create an AES key with:

```kotlin
KeyGenParameterSpec.Builder(
    KEY_ALIAS,
    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
)
    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
    .setRandomizedEncryptionRequired(true)
    .build()
```

Store Base64 of version byte + 12-byte IV + ciphertext/tag in private SharedPreferences. On `AEADBadTagException`, return null and remove the corrupt value. Never log decrypted strings.

- [ ] **Step 5: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.search.*'
git add app/src/main/AndroidManifest.xml app/build.gradle.kts \
  app/src/main/java/tw/daniel/epubword/cover/search app/src/test \
  app/src/main/java/tw/daniel/epubword/ui/ConverterScreen.kt
git commit -m "feat: secure Android cover-search credentials"
```

Expected: PASS.

---

### Task 6: Add Android candidate search and selection UI

**Files:**
- Create: `app/src/main/java/tw/daniel/epubword/cover/search/CoverSearchModels.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/search/CoverSearchViewModel.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverSearchScreen.kt`
- Create: `app/src/main/java/tw/daniel/epubword/cover/ui/SearchCredentialDialog.kt`
- Modify: `app/src/main/java/tw/daniel/epubword/cover/ui/CoverEditorScreen.kt`
- Create: `app/src/test/java/tw/daniel/epubword/cover/search/CoverSearchViewModelTest.kt`
- Create: `app/src/androidTest/java/tw/daniel/epubword/cover/ui/CoverSearchScreenTest.kt`

**Interfaces:**
- Modes: `PUBLIC_BOOKS`, `GENERAL_IMAGE`.
- Multiple candidates displayed in a lazy adaptive grid.
- Selecting a candidate downloads/copies it, then asks `只放正面` or `延伸整張書封`.

- [ ] **Step 1: Write failing mode/credential tests**

```kotlin
@Test fun publicSearchDoesNotRequireCredential() = runTest {
    val vm = createSearchViewModel(credential = null)
    vm.search(SearchMode.PUBLIC_BOOKS)
    advanceUntilIdle()
    assertNull(vm.uiState.value.credentialError)
}

@Test fun generalSearchRequiresCredentialBeforeGatewayCall() = runTest {
    val gateway = FakeSearchGateway()
    val vm = createSearchViewModel(gateway = gateway, credential = null)
    vm.search(SearchMode.GENERAL_IMAGE)
    assertEquals("請先設定 Google API Key 與 Search Engine ID。", vm.uiState.value.credentialError)
    assertEquals(0, gateway.searchCalls)
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
gradle --no-daemon testDebugUnitTest \
  --tests 'tw.daniel.epubword.cover.search.CoverSearchViewModelTest'
```

Expected: compilation failure.

- [ ] **Step 3: Implement candidate JSON parsing and state machine**

Statuses: idle, searching, results, downloading, error. Candidate models include source page, dimensions, provider, rights text, preview URL, image URL. Do not store credentials in `CoverSearchUiState`; load them at call time and immediately pass to gateway.

```kotlin
enum class CoverSearchStatus { IDLE, SEARCHING, RESULTS, DOWNLOADING, ERROR }

data class CoverSearchCandidate(
    val id: String,
    val provider: String,
    val title: String?,
    val author: String?,
    val previewUrl: String,
    val imageUrl: String,
    val sourcePage: String,
    val width: Int?,
    val height: Int?,
    val rightsText: String?,
)

data class CoverSearchUiState(
    val status: CoverSearchStatus = CoverSearchStatus.IDLE,
    val query: String = "",
    val candidates: List<CoverSearchCandidate> = emptyList(),
    val errorMessage: String? = null,
    val selectedCandidateId: String? = null,
)

fun searchPublic() {
    val request = buildRequest(providerMode = "public")
    runSearch(request, credential = null)
}

fun searchGeneral(useOnce: ProviderCredential? = null) {
    val credential = useOnce ?: credentialStore.load()
        ?: return _uiState.update { it.copy(errorMessage = "請輸入 API Key 與 Search Engine ID。") }
    runSearch(buildRequest(providerMode = "google_custom"), credential)
}

private fun runSearch(request: JSONObject, credential: ProviderCredential?) {
    viewModelScope.launch {
        _uiState.update { it.copy(status = CoverSearchStatus.SEARCHING, errorMessage = null) }
        runCatching { gateway.search(request, credential) }
            .onSuccess { result -> _uiState.update { it.copy(status = CoverSearchStatus.RESULTS, candidates = result) } }
            .onFailure { failure -> _uiState.update { it.copy(status = CoverSearchStatus.ERROR, errorMessage = failure.message) } }
    }
}
```

- [ ] **Step 4: Build candidate grid with Coil**

Each card shows:

- preview image;
- title/author or source domain;
- known resolution;
- provider badge;
- source link action;
- rights text or default warning;
- Select button.

Use `LazyVerticalGrid(GridCells.Adaptive(140.dp))`. Coil disk cache handles preview URLs; selected originals still pass through shared validation/download.

```kotlin
@Composable
fun CandidateGrid(
    candidates: List<CoverSearchCandidate>,
    onOpenSource: (String) -> Unit,
    onSelect: (CoverSearchCandidate) -> Unit,
) {
    LazyVerticalGrid(
        columns = GridCells.Adaptive(140.dp),
        contentPadding = PaddingValues(12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(candidates, key = { it.id }) { candidate ->
            Card {
                Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    AsyncImage(
                        model = candidate.previewUrl,
                        contentDescription = candidate.title ?: "封面候選圖",
                        modifier = Modifier.fillMaxWidth().aspectRatio(0.68f),
                        contentScale = ContentScale.Crop,
                    )
                    Text(candidate.title ?: URI(candidate.sourcePage).host.orEmpty(), maxLines = 2)
                    Text(
                        candidate.width?.let { width -> "${width} × ${candidate.height ?: 0}" } ?: "解析度未知",
                        style = MaterialTheme.typography.labelSmall,
                    )
                    AssistChip(onClick = {}, label = { Text(candidate.provider) })
                    Text(
                        candidate.rightsText ?: "授權狀態未確認；使用者需自行確認使用權",
                        style = MaterialTheme.typography.labelSmall,
                    )
                    TextButton(onClick = { onOpenSource(candidate.sourcePage) }) { Text("查看來源") }
                    Button(onClick = { onSelect(candidate) }, modifier = Modifier.fillMaxWidth()) { Text("選擇") }
                }
            }
        }
    }
}
```

- [ ] **Step 5: Add credential dialog and explicit general-search action**

Mask API Key by default with reveal toggle. Search Engine ID remains visible. Buttons: Save locally, Use once, Clear saved. `Use once` stays only in ViewModel memory and is cleared when leaving search.

```kotlin
@Composable
fun SearchCredentialDialog(
    initial: ProviderCredential?,
    onSave: (ProviderCredential) -> Unit,
    onUseOnce: (ProviderCredential) -> Unit,
    onClear: () -> Unit,
    onDismiss: () -> Unit,
) {
    var apiKey by remember { mutableStateOf(initial?.apiKey.orEmpty()) }
    var searchEngineId by remember { mutableStateOf(initial?.searchEngineId.orEmpty()) }
    var reveal by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Google 圖片搜尋憑證") },
        text = {
            Column {
                OutlinedTextField(
                    apiKey,
                    { apiKey = it },
                    label = { Text("API Key") },
                    visualTransformation = if (reveal) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = { IconButton(onClick = { reveal = !reveal }) { Icon(Icons.Default.Visibility, null) } },
                )
                OutlinedTextField(searchEngineId, { searchEngineId = it }, label = { Text("Search Engine ID") })
            }
        },
        confirmButton = {
            Row {
                TextButton(onClick = { onClear() }) { Text("清除已儲存") }
                TextButton(onClick = { onUseOnce(ProviderCredential(apiKey, searchEngineId)) }) { Text("僅本次使用") }
                Button(onClick = { onSave(ProviderCredential(apiKey, searchEngineId)) }) { Text("儲存在本機") }
            }
        },
    )
}
```

```kotlin
override fun onCleared() {
    oneTimeCredential = null
    super.onCleared()
}
```

- [ ] **Step 6: Integrate selected image into editor**

After download, show mode chooser. Patch/add the image element and switch project `image_mode`; preserve separate crop parameters for front-only and full-spread in content keys `front_crop` and `spread_crop`.

```kotlin
fun applyDownloadedCandidate(path: String, mode: ImageMode) {
    val project = requireNotNull(currentProject)
    val existing = project.elements.firstOrNull { it.id == "cover-art" }
    val content = (existing?.content ?: JSONObject())
        .put("path", path)
        .put("fit", "cover")
        .put("front_crop", existing?.content?.optJSONObject("front_crop") ?: defaultCropJson())
        .put("spread_crop", existing?.content?.optJSONObject("spread_crop") ?: defaultCropJson())
    val element = existing?.copy(content = content) ?: CoverElement(
        id = "cover-art",
        kind = ElementKind.IMAGE,
        region = if (mode == ImageMode.FRONT_ONLY) CoverRegion.FRONT else CoverRegion.SPREAD,
        transform = imageRectForMode(project, mode),
        zIndex = -100,
        opacity = 1.0,
        content = content,
    )
    commitProject(
        project.copy(
            imageMode = mode,
            elements = project.elements.filterNot { it.id == element.id } + element,
        )
    )
}
```

- [ ] **Step 7: Run tests and commit**

```bash
gradle --no-daemon testDebugUnitTest compileDebugAndroidTestKotlin
git add app/src/main/java/tw/daniel/epubword/cover app/src/test app/src/androidTest
git commit -m "feat: add Android multi-candidate cover search"
```

Expected: PASS.

---
