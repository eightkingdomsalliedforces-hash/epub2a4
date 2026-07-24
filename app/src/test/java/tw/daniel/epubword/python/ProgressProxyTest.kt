package tw.daniel.epubword.python

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicBoolean

class ProgressProxyTest {
    @Test
    fun `progress callback is forwarded exactly once and clamped`() {
        var callCount = 0
        var receivedPercent = -1
        var receivedMessage = ""
        val cancellation = AtomicBoolean(false)
        val proxy = PythonConversionGateway.ProgressProxy(cancellation) { percent, message ->
            callCount += 1
            receivedPercent = percent
            receivedMessage = message
        }

        proxy.onProgress(140, "正在轉換")

        assertEquals(1, callCount)
        assertEquals(100, receivedPercent)
        assertEquals("正在轉換", receivedMessage)
        assertFalse(proxy.isCancelled())

        cancellation.set(true)
        assertTrue(proxy.isCancelled())
    }
}
