package tw.daniel.epubword.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class AppRouteStateTest {
    @Test
    fun startsAtHome() {
        assertEquals(AppRoute.HOME, AppRouteState().route)
    }

    @Test
    fun openCoverStartsAtSetup() {
        val state = AppRouteState().navigate(AppRoute.COVER_SETUP)
        assertEquals(AppRoute.COVER_SETUP, state.route)
    }

    @Test
    fun navigationKeepsCoverHandoffUntilReplaced() {
        val handoff = CoverHandoffToken("session-1")
        val state = AppRouteState(coverHandoff = handoff)
            .navigate(AppRoute.CONVERTER)
        assertEquals(handoff, state.coverHandoff)
    }
}
