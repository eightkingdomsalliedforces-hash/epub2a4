# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]
PYTHON_SRC = PROJECT_ROOT / "python" / "src"
ANDROID_PYTHON_SRC = PROJECT_ROOT / "app" / "src" / "main" / "python"
ENTRY_POINT = PYTHON_SRC / "epub_a4_word_desktop" / "__main__.py"


datas = []
binaries = []
hiddenimports = []

for package_name in (
    "epub_a4_word",
    "epub_a4_word_desktop",
    "PIL",
    "bs4",
    "docx",
    "pypdf",
    "keyring",
    "platformdirs",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

hiddenimports += collect_submodules("lxml")

analysis = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(PYTHON_SRC), str(ANDROID_PYTHON_SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytestqt", "tkinter.test", "unittest.test"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="EPUB2A4",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

portable = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EPUB2A4-Windows-Portable-x64",
)
