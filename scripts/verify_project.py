#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def require(path: str) -> Path:
    target = ROOT / path
    if not target.exists():
        errors.append(f"missing: {path}")
    return target


required = [
    "settings.gradle.kts",
    "build.gradle.kts",
    "app/build.gradle.kts",
    "app/src/main/AndroidManifest.xml",
    "app/src/main/python/android_bridge.py",
    "python/src/epub_a4_word/__init__.py",
    "python/src/epub_a4_word/epub_structure.py",
    "python/src/epub_a4_word/cover/search/query_plan.py",
    "python/src/epub_a4_word/cover/search/wikidata.py",
    "python/src/epub_a4_word/cover/search/gutendex.py",
    "python/src/epub_a4_word/cover/search/alias_cache.py",
    "python/src/epub_a4_word/cover/search/pipeline.py",
    "python/src/epub_a4_word_desktop/cover/search_controller.py",
    "python/src/epub_a4_word_desktop/cover/search_panel.py",
    "python/src/epub_a4_word_desktop/pages/converter_page.py",
    "app/src/main/java/tw/daniel/epubword/MainActivity.kt",
    "app/src/main/java/tw/daniel/epubword/ui/ConverterScreen.kt",
    "app/src/main/java/tw/daniel/epubword/ui/ConversionViewModel.kt",
    "app/src/main/java/tw/daniel/epubword/python/PythonConversionGateway.kt",
]
for item in required:
    require(item)

app_gradle = require("app/build.gradle.kts").read_text(encoding="utf-8")
checks = {
    "compileSdk 36": r"compileSdk\s*=\s*36",
    "minSdk 24": r"minSdk\s*=\s*24",
    "targetSdk 36": r"targetSdk\s*=\s*36",
    "arm64 only": r"abiFilters\s*\+=\s*listOf\(\"arm64-v8a\"\)",
    "Python 3.13": r"version\s*=\s*\"3\.13\"",
    "Chaquopy plugin": r"com\.chaquo\.python",
    "lxml Android dependency": r"lxml==5\.3\.0",
    "Pillow Android dependency": r"Pillow==11\.0\.0",
    "pypdf Android dependency": r"pypdf==6\.14\.2",
    "canonical Python source set": r"srcDir\(\"\.\./python/src\"\)",
}
for label, pattern in checks.items():
    if not re.search(pattern, app_gradle):
        errors.append(f"Gradle check failed: {label}")

chaquopy_index = app_gradle.find("chaquopy {")
canonical_source_index = app_gradle.find('srcDir("../python/src")')
if chaquopy_index < 0 or canonical_source_index < chaquopy_index:
    errors.append("Gradle check failed: canonical Python source set must be inside chaquopy")

manifest_path = require("app/src/main/AndroidManifest.xml")
try:
    manifest = ET.parse(manifest_path).getroot()
    permissions = [
        node.attrib.get("{http://schemas.android.com/apk/res/android}name", "")
        for node in manifest.findall("uses-permission")
    ]
    forbidden = {
        "android.permission.INTERNET",
        "android.permission.MANAGE_EXTERNAL_STORAGE",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
    }
    found = sorted(forbidden.intersection(permissions))
    if found:
        errors.append("forbidden permissions: " + ", ".join(found))
except ET.ParseError as exc:
    errors.append(f"manifest XML invalid: {exc}")

# Every committed Python file must parse, including the desktop package.
python_roots = (ROOT / "python/src", ROOT / "app/src/main/python")
parsed_files: dict[Path, ast.AST] = {}
for python_root in python_roots:
    for python_file in python_root.rglob("*.py"):
        try:
            parsed_files[python_file] = ast.parse(
                python_file.read_text(encoding="utf-8"),
                filename=str(python_file),
            )
        except SyntaxError as exc:
            errors.append(f"Python syntax error: {exc}")

# Tkinter is allowed only in the explicitly separate desktop package. The
# shared cover/conversion core and Android bridge must stay GUI-toolkit free.
android_compatible_roots = (
    ROOT / "python/src/epub_a4_word",
    ROOT / "app/src/main/python",
)
for python_root in android_compatible_roots:
    for python_file in python_root.rglob("*.py"):
        tree = parsed_files.get(python_file)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                if any(name.startswith("tkinter") for name in names):
                    errors.append(f"desktop GUI import in Android Python: {python_file}")

legacy_core = ROOT / "app/src/main/python/epub_a4_word"
if legacy_core.exists():
    errors.append("duplicate Android-only Python core remains: app/src/main/python/epub_a4_word")

for kotlin_file in (ROOT / "app/src/main/java").rglob("*.kt"):
    text = kotlin_file.read_text(encoding="utf-8")
    if not re.search(r"^package\s+tw\.daniel\.epubword", text, re.MULTILINE):
        errors.append(f"unexpected Kotlin package: {kotlin_file}")
    if "TODO(" in text or "NotImplementedError" in text:
        errors.append(f"unfinished Kotlin code: {kotlin_file}")

for fixture in ["test-fixtures/minimal.epub", "test-fixtures/A4_test_document.docx"]:
    path = require(fixture)
    if path.exists():
        try:
            with ZipFile(path) as archive:
                if not archive.namelist():
                    errors.append(f"empty ZIP fixture: {fixture}")
        except BadZipFile:
            errors.append(f"invalid ZIP fixture: {fixture}")

bridge = require("app/src/main/python/android_bridge.py").read_text(encoding="utf-8")
for token in ["convert_file", "convert_file_json", "probe", "ConversionCancelled"]:
    if token not in bridge:
        errors.append(f"bridge API missing: {token}")

workflow = require(".github/workflows/android.yml").read_text(encoding="utf-8")
workflow_checks = {
    "Android SDK setup": "android-actions/setup-android@v3",
    "Android platform 36 install": 'sdkmanager "platforms;android-36"',
    "debug APK build": "assembleDebug",
    "16 KB zipalign verification": '"$ZIPALIGN" -c -P 16',
}
for label, token in workflow_checks.items():
    if token not in workflow:
        errors.append(f"workflow check failed: {label}")

if errors:
    print("Project verification failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("Project verification passed")
print("- API 24–36")
print("- arm64-v8a only")
print("- no network or broad storage permissions")
print("- shared, desktop, and Android bridge Python sources parse successfully")
print("- EPUB cover-role and free multilingual search modules are present")
print("- EPUB and DOCX fixtures are valid ZIP containers")
