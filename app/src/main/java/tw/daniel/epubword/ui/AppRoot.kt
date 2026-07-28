package tw.daniel.epubword.ui

import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import tw.daniel.epubword.cover.model.CoverHandoff
import tw.daniel.epubword.cover.ui.CoverEditorCallbacks
import tw.daniel.epubword.cover.ui.CoverEditorScreen
import tw.daniel.epubword.cover.ui.CoverSetupCallbacks
import tw.daniel.epubword.cover.ui.CoverSetupScreen
import tw.daniel.epubword.cover.ui.CoverStatus
import tw.daniel.epubword.cover.ui.CoverUiState
import tw.daniel.epubword.model.MarginMode
import tw.daniel.epubword.model.OutputMode
import tw.daniel.epubword.model.WritingPreset

enum class AppRoute { HOME, CONVERTER, COVER_SETUP, COVER_EDITOR }

data class AppRouteState(val route: AppRoute = AppRoute.HOME) {
    fun navigate(next: AppRoute): AppRouteState = copy(route = next)
}

@Composable
fun AppRoot(
    conversionState: ConversionUiState,
    onChooseConversionSource: () -> Unit,
    onOutputMode: (OutputMode) -> Unit,
    onWritingPreset: (WritingPreset) -> Unit,
    onMarginMode: (MarginMode) -> Unit,
    onFontName: (String) -> Unit,
    onBodyFontSize: (Double) -> Unit,
    onHeadingFontSize: (Double) -> Unit,
    onPageNumbers: (Boolean) -> Unit,
    onCutGuides: (Boolean) -> Unit,
    onContentOnly: (Boolean) -> Unit,
    onConvert: () -> Unit,
    onCancelConversion: () -> Unit,
    onSaveConversion: () -> Unit,
    onDismissConversionError: () -> Unit,
    onRequestCoverHandoff: () -> Unit = {},
    onOpenCoverHandoff: (CoverHandoff) -> Unit = {},
    onMarkCoverHandoffHandled: (Long) -> Unit = {},
    coverState: CoverUiState = CoverUiState(),
    coverCallbacks: CoverSetupCallbacks = CoverSetupCallbacks(),
    coverEditorCallbacks: CoverEditorCallbacks = CoverEditorCallbacks(),
) {
    var routeName by rememberSaveable { mutableStateOf(AppRoute.HOME.name) }
    val route = runCatching { AppRoute.valueOf(routeName) }.getOrDefault(AppRoute.HOME)
    fun navigate(next: AppRoute) {
        routeName = next.name
    }

    LaunchedEffect(
        conversionState.coverHandoffRequestId,
        conversionState.handledCoverHandoffRequestId,
        conversionState.coverHandoff,
    ) {
        val handoff = conversionState.coverHandoff
        if (
            handoff != null &&
            conversionState.coverHandoffRequestId > conversionState.handledCoverHandoffRequestId
        ) {
            val requestId = conversionState.coverHandoffRequestId
            onOpenCoverHandoff(handoff)
            onMarkCoverHandoffHandled(requestId)
            navigate(AppRoute.COVER_SETUP)
        }
    }

    LaunchedEffect(coverState.projectJson, coverState.status) {
        if (coverState.projectJson.isNotBlank() && coverState.status in setOf(
                CoverStatus.EDITING,
                CoverStatus.RENDERING,
                CoverStatus.EXPORTING,
                CoverStatus.READY_TO_SAVE,
                CoverStatus.SAVING,
                CoverStatus.COMPLETED,
            )
        ) {
            navigate(AppRoute.COVER_EDITOR)
        }
    }

    BackHandler(enabled = route != AppRoute.HOME) {
        navigate(if (route == AppRoute.COVER_EDITOR) AppRoute.COVER_SETUP else AppRoute.HOME)
    }

    when (route) {
        AppRoute.HOME -> HomeScreen(
            onOpenConverter = { navigate(AppRoute.CONVERTER) },
            onOpenCover = { navigate(AppRoute.COVER_SETUP) },
        )
        AppRoute.CONVERTER -> ConverterScreen(
            state = conversionState,
            onChooseInput = onChooseConversionSource,
            onOutputMode = onOutputMode,
            onWritingPreset = onWritingPreset,
            onMarginMode = onMarginMode,
            onFontName = onFontName,
            onBodyFontSize = onBodyFontSize,
            onHeadingFontSize = onHeadingFontSize,
            onPageNumbers = onPageNumbers,
            onCutGuides = onCutGuides,
            onContentOnly = onContentOnly,
            onConvert = onConvert,
            onCancel = onCancelConversion,
            onSave = onSaveConversion,
            onDismissError = onDismissConversionError,
            onCreateCover = onRequestCoverHandoff,
        )
        AppRoute.COVER_SETUP -> CoverSetupScreen(
            state = coverState,
            callbacks = coverCallbacks,
        )
        AppRoute.COVER_EDITOR -> CoverEditorScreen(
            state = coverState,
            callbacks = coverEditorCallbacks.copy(
                onBack = { navigate(AppRoute.COVER_SETUP) },
            ),
        )
    }
}
