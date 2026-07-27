from __future__ import annotations


def test_android_bridge_forces_docx_story_fallback(monkeypatch) -> None:
    import android_bridge

    calls: list[bool] = []

    def fake_install(*, force: bool = False) -> bool:
        calls.append(force)
        return True

    monkeypatch.setattr(android_bridge, "install_story_template_fallbacks", fake_install)

    assert android_bridge._install_android_docx_compat() is True
    assert calls == [True]
