package tw.daniel.epubword.python

import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.withContext
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

/** Runs Chaquopy work on one dedicated thread with an explicit 8 MiB stack. */
class LargeStackPythonExecutor : AutoCloseable {
    private val executor = Executors.newSingleThreadExecutor { runnable ->
        Thread(
            null,
            runnable,
            "epub2a4-python-${THREAD_ID.incrementAndGet()}",
            STACK_BYTES,
        )
    }
    private val dispatcher = executor.asCoroutineDispatcher()

    fun <T> run(block: () -> T): T = executor.submit(Callable(block)).get()

    suspend fun <T> runSuspending(block: () -> T): T = withContext(dispatcher) {
        block()
    }

    override fun close() {
        dispatcher.close()
    }

    private companion object {
        const val STACK_BYTES = 8L * 1024L * 1024L
        val THREAD_ID = AtomicLong(0)
    }
}
