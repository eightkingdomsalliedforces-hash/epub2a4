from pathlib import Path


def test_core_has_one_committed_source_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "python/src/epub_a4_word/__init__.py").is_file()
    assert not (root / "app/src/main/python/epub_a4_word").exists()


def test_android_bridge_imports_canonical_core() -> None:
    import android_bridge

    result = android_bridge.probe()
    assert result["python_core_version"]
    assert result["bridge_version"] == "1.0"


def test_python_package_version_matches_pyproject() -> None:
    import tomllib

    from epub_a4_word import __version__

    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"]


def test_chaquopy_uses_canonical_python_source_set() -> None:
    root = Path(__file__).resolve().parents[1]
    gradle = (root / "app/build.gradle.kts").read_text(encoding="utf-8")
    chaquopy_block = gradle.split("chaquopy {", 1)[1]
    assert 'sourceSets {' in chaquopy_block
    assert 'srcDir("../python/src")' in chaquopy_block


def test_project_verifier_requires_new_epub_and_search_modules() -> None:
    root = Path(__file__).resolve().parents[1]
    verifier = (root / "scripts/verify_project.py").read_text(encoding="utf-8")
    for required_path in (
        "python/src/epub_a4_word/epub_structure.py",
        "python/src/epub_a4_word/cover/search/query_plan.py",
        "python/src/epub_a4_word/cover/search/wikidata.py",
        "python/src/epub_a4_word/cover/search/gutendex.py",
        "python/src/epub_a4_word/cover/search/alias_cache.py",
        "python/src/epub_a4_word/cover/search/pipeline.py",
    ):
        assert required_path in verifier
