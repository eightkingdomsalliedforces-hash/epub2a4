from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "app/src/main/java/tw/daniel/epubword/python/PythonConversionGateway.kt"
VIEW_MODEL = ROOT / "app/src/main/java/tw/daniel/epubword/ui/ConversionViewModel.kt"


def test_python_conversion_uses_a_dedicated_large_stack_thread():
    gateway = GATEWAY.read_text(encoding="utf-8")

    assert "suspend fun convert(" in gateway
    assert "asCoroutineDispatcher" in gateway
    assert re.search(r"Thread\(\s*null,\s*runnable,", gateway)
    assert "8L * 1024L * 1024L" in gateway


def test_view_model_does_not_run_python_on_dispatchers_io():
    view_model = VIEW_MODEL.read_text(encoding="utf-8")

    assert "withContext(Dispatchers.IO) {\n                    gateway.convert(" not in view_model
    assert "gateway.close()" in view_model
