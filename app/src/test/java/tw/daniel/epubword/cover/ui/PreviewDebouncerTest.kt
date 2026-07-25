package tw.daniel.epubword.cover.ui

import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test

class PreviewDebouncerTest {
    @Test
    fun onlyLatestPreviewRequestRunsAfterDelay() = runBlocking {
        val rendered = mutableListOf<String>()
        val debouncer = PreviewDebouncer(this, delayMillis = 150) { rendered += it }

        debouncer.schedule("first")
        delay(50)
        debouncer.schedule("second")
        delay(180)

        assertEquals(listOf("second"), rendered)
        debouncer.cancel()
    }
}
