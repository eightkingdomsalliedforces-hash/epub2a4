from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "app/src/main/java/tw/daniel/epubword/python/PythonConversionGateway.kt"
EXECUTOR = ROOT / "app/src/main/java/tw/daniel/epubword/python/LargeStackPythonExecutor.kt"
VIEW_MODEL = ROOT / "app/src/main/java/tw/daniel/epubword/ui/ConversionViewModel.kt"


def test_python_conversion_uses_the_shared_dedicated_large_stack_executor():
    gateway = GATEWAY.read_text(encoding="utf-8")
    executor = EXECUTOR.read_text(encoding="utf-8")

    assert "suspend fun convert(" in gateway
    assert "LargeStackPythonExecutor" in gateway
    assert "executor.runSuspending" in gateway
    assert "asCoroutineDispatcher" in executor
    assert "Thread(" in executor
    assert "epub2a4-python-" in executor
    assert "8L * 1024L * 1024L" in executor


def test_view_model_does_not_run_python_on_dispatchers_io():
    view_model = VIEW_MODEL.read_text(encoding="utf-8")

    assert "withContext(Dispatchers.IO) {\n                    gateway.convert(" not in view_model
    assert "gateway.close()" in view_model
