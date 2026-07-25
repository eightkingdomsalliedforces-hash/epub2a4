package tw.daniel.epubword.python

import org.junit.Assert.assertTrue
import org.junit.Test

class LargeStackPythonExecutorTest {
    @Test
    fun executorRunsOnDedicatedNamedThread() {
        LargeStackPythonExecutor().use { executor ->
            val name = executor.run { Thread.currentThread().name }
            assertTrue(name.startsWith("epub2a4-python-"))
        }
    }
}
