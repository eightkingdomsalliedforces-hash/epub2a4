package tw.daniel.epubword.cover.ui

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Keeps only the latest expensive preview request. Cancellation is cooperative:
 * an already-running Python render may finish, but stale results are still
 * discarded by CoverViewModel's generation check.
 */
class PreviewDebouncer(
    private val scope: CoroutineScope,
    private val delayMillis: Long = 250L,
    private val render: suspend (String) -> Unit,
) {
    private var pending: Job? = null

    init {
        require(delayMillis >= 0L) { "預覽延遲不可為負數。" }
    }

    @Synchronized
    fun schedule(projectJson: String) {
        pending?.cancel()
        pending = scope.launch {
            delay(delayMillis)
            render(projectJson)
        }
    }

    @Synchronized
    fun cancel() {
        pending?.cancel()
        pending = null
    }
}
