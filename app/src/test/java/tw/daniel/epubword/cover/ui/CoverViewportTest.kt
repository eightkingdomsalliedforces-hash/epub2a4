package tw.daniel.epubword.cover.ui

import androidx.compose.ui.geometry.Offset
import org.junit.Assert.assertEquals
import org.junit.Test

class CoverViewportTest {
    @Test
    fun mmRoundTripIsStable() {
        val viewport = CoverViewport(scalePxPerMm = 4.0, offsetPx = Offset(20f, 30f))
        val screen = viewport.mmToScreen(Offset(12.5f, 18.75f))
        val restored = viewport.screenToMm(screen)

        assertEquals(12.5f, restored.x, 0.0001f)
        assertEquals(18.75f, restored.y, 0.0001f)
    }

    @Test
    fun zoomIsClamped() {
        assertEquals(0.1, CoverViewport(scalePxPerMm = 0.01).normalized().scalePxPerMm, 0.0001)
        assertEquals(8.0, CoverViewport(scalePxPerMm = 1000.0).normalized().scalePxPerMm, 0.0001)
    }

    @Test
    fun fitScaleLeavesEightPercentMargin() {
        assertEquals(4.6, fitScalePxPerMm(1000f, 800f, 200.0, 160.0), 0.0001)
    }
}
