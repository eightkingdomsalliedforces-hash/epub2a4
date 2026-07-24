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
