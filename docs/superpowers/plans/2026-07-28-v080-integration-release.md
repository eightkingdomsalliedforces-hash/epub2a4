# v0.8.0 Integration and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the approved vertical typesetting and balanced spine work, verify both applications, merge, and publish the automatically generated `v0.8.0` release assets.

**Architecture:** Version and documentation changes happen only after both feature plans pass their focused suites. The repository’s existing tag-triggered GitHub Actions release workflow remains the publisher; this plan verifies its three required assets rather than manually uploading alternate builds.

**Tech Stack:** Git, GitHub Actions, pytest, Gradle, PyInstaller packaging verification, GitHub CLI/API

## Global Constraints

- Execute only after `2026-07-28-taiwan-vertical-typesetting.md` and `2026-07-28-balanced-publisher-spine.md` are complete.
- Release version is exactly `0.8.0`; Git tag is exactly `v0.8.0`.
- All Python, Desktop, and Android tests must pass.
- Windows Portable smoke verification must pass.
- Release is created automatically by pushing the version tag.
- Required release assets are `EPUB2A4-Android.apk`, `EPUB2A4-Windows-Portable-x64.zip`, and `SHA256SUMS.txt`.
- Do not commit local-only `local.properties` or `uv.lock`.

---

### Task 1: Version metadata and user-facing changelog

**Files:**
- Modify: `pyproject.toml`
- Modify: `python/src/epub_a4_word/__init__.py`
- Modify: `app/build.gradle.kts`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Test: `scripts/verify_project.py`
- Test: `scripts/kotlin_model_smoke.kt`

**Interfaces:**
- Python package version: `0.8.0`
- Android `versionName`: `0.8.0`
- Android `versionCode`: `9`

- [ ] **Step 1: Write the expected version assertions**

Extend `scripts/verify_project.py` to read the three version sources and fail
unless all report `0.8.0`; extend the Kotlin smoke script to assert
`WritingPreset.TAIWAN_VERTICAL` maps to `taiwan_vertical/right`.

- [ ] **Step 2: Run verification and confirm it fails on 0.7.0**

Run: `python scripts/verify_project.py`

Expected: FAIL with a version mismatch.

- [ ] **Step 3: Bump versions**

Set:

```toml
# pyproject.toml
version = "0.8.0"
```

```python
# python/src/epub_a4_word/__init__.py
__version__ = "0.8.0"
```

```kotlin
// app/build.gradle.kts
versionCode = 9
versionName = "0.8.0"
```

- [ ] **Step 4: Document the shipped behavior**

Move the current `Unreleased` entries under `## 0.8.0 — 2026-07-28` and add
concise bullets for:

- selectable Taiwan vertical/right-bound and horizontal/left-bound layouts;
- native Word vertical English/number handling;
- upright images and page numbers on image-only pages;
- the single page-number switch for manga;
- Desktop and Android direction controls;
- balanced reference spine, logo-only top, one publisher name, accent volume
  badge, and bounded width degradation.

Update README conversion controls and compatibility note.

- [ ] **Step 5: Run version verification**

Run: `python scripts/verify_project.py`

Expected: PASS.

- [ ] **Step 6: Commit version and documentation**

```bash
git add pyproject.toml python/src/epub_a4_word/__init__.py app/build.gradle.kts CHANGELOG.md README.md scripts/verify_project.py scripts/kotlin_model_smoke.kt
git commit -m "chore: prepare v0.8.0"
```

---

### Task 2: Complete local verification

**Files:**
- Verify only; repair failures in the file that owns the failed behavior and add a regression before recommitting.

**Interfaces:**
- Produces a clean, release-ready commit with no untracked build artifacts staged.

- [ ] **Step 1: Run source and whitespace checks**

Run: `git diff --check`

Run: `python scripts/verify_project.py`

Expected: both exit 0.

- [ ] **Step 2: Run all Python and Desktop tests**

Run: `python -m pytest python-tests desktop/tests -q`

Expected: PASS with no failures.

- [ ] **Step 3: Run Android unit tests and build**

Run: `gradle --no-daemon :app:testDebugUnitTest :app:assembleDebug`

Expected: BUILD SUCCESSFUL and an APK at
`app/build/outputs/apk/debug/app-debug.apk`.

- [ ] **Step 4: Build and smoke-test Windows Portable**

Run: `python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec`

Run: `python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64`

Expected: both exit 0.

- [ ] **Step 5: Inspect repository state**

Run: `git status --short`

Expected: only known local-only `local.properties` and `uv.lock` may remain
untracked; no feature, test, version, or documentation change is unstaged.

---

### Task 3: Review, merge, tag, and automatic release

**Files:**
- No source edits.

**Interfaces:**
- Produces merged `main`, annotated/pushed `v0.8.0`, and the three required release assets.

- [ ] **Step 1: Request final code review**

Use `superpowers:requesting-code-review` against the complete branch diff.
Resolve every correctness or release-blocking finding, rerun the affected
focused tests, and then rerun Task 2.

- [ ] **Step 2: Push the feature branch and open/update the pull request**

```bash
git push -u origin feat/taiwan-vertical-layout-v080
gh pr create --base main --head feat/taiwan-vertical-layout-v080 --title "feat: add Taiwan vertical layout and balanced spine" --body-file .github/PULL_REQUEST_TEMPLATE.md
```

If no PR template exists, use `gh pr create --fill` and edit the body to list
the three local verification commands and their results.

- [ ] **Step 3: Wait for required checks and merge**

Run: `gh pr checks --watch`

Expected: Android, Desktop, and Windows workflows all pass.

Run: `gh pr merge --squash --delete-branch`

Expected: PR reports merged.

- [ ] **Step 4: Tag the exact merged commit**

```bash
git fetch origin main --tags
git tag -a v0.8.0 origin/main -m "v0.8.0"
git push origin v0.8.0
```

Confirm `git rev-list -n 1 v0.8.0` equals
`git rev-parse origin/main`.

- [ ] **Step 5: Wait for the tag-triggered release workflow**

Run: `gh run list --workflow release.yml --limit 5`

Identify the run whose event is `push` and head branch/tag is `v0.8.0`, then:

```bash
gh run watch <run-id> --exit-status
```

Expected: Windows, Android, and release jobs all succeed.

- [ ] **Step 6: Verify release assets and checksums**

```bash
gh release view v0.8.0 --json url,tagName,assets
gh release download v0.8.0 --dir .release-v0.8.0
```

Assert the downloaded directory contains exactly the required named assets,
then verify `SHA256SUMS.txt` against both binaries using the platform
checksum tool. Remove only the temporary `.release-v0.8.0` verification
directory after confirming its resolved path is inside the worktree.

- [ ] **Step 7: Report the release**

Provide:

- merged PR URL;
- merged commit SHA;
- release URL;
- successful workflow run URL;
- exact test totals from Task 2;
- the three verified asset names.

