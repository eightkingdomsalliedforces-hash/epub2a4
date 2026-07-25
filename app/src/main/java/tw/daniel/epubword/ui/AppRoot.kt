package tw.daniel.epubword.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import tw.daniel.epubword.cover.ui.CoverSetupCallbacks
import tw.daniel.epubword.cover.ui.CoverSetupScreen
import tw.daniel.epubword.cover.ui.CoverUiState
import tw.daniel.epubword.model.MarginMode
import tw.daniel.epubword.model.OutputMode

enum class AppRoute { HOME, CONVERTER, COVER_SETUP, COVER_EDITOR }

data class AppRouteState(val route: AppRoute = AppRoute.HOME) {
    fun navigate(next: AppRoute): AppRouteState = copy(route = next)
}

@Composable
fun AppRoot(
    conversionState: ConversionUiState,
    onChooseConversionSource: () -> Unit,
    onOutputMode: (OutputMode) -> Unit,
    onMarginMode: (MarginMode) -> Unit,
    onFontName: (String) -> Unit,
    onBodyFontSize: (Double) -> Unit,
    onHeadingFontSize: (Double) -> Unit,
    onPageNumbers: (Boolean) -> Unit,
    onCutGuides: (Boolean) -> Unit,
    onConvert: () -> Unit,
    onCancelConversion: () -> Unit,
    onSaveConversion: () -> Unit,
    onDismissConversionError: () -> Unit,
    coverState: CoverUiState = CoverUiState(),
    coverCallbacks: CoverSetupCallbacks = CoverSetupCallbacks(),
) {
    var routeName by rememberSaveable { mutableStateOf(AppRoute.HOME.name) }
    val route = runCatching { AppRoute.valueOf(routeName) }.getOrDefault(AppRoute.HOME)
    fun navigate(next: AppRoute) {
        routeName = next.name
    }

    BackHandler(enabled = route != AppRoute.HOME) { navigate(AppRoute.HOME) }

    when (route) {
        AppRoute.HOME -> HomeScreen(
            onOpenConverter = { navigate(AppRoute.CONVERTER) },
            onOpenCover = { navigate(AppRoute.COVER_SETUP) },
        )
        AppRoute.CONVERTER -> ConverterScreen(
            state = conversionState,
            onChooseInput = onChooseConversionSource,
            onOutputMode = onOutputMode,
            onMarginMode = onMarginMode,
            onFontName = onFontName,
            onBodyFontSize = onBodyFontSize,
            onHeadingFontSize = onHeadingFontSize,
            onPageNumbers = onPageNumbers,
            onCutGuides = onCutGuides,
            onConvert = onConvert,
            onCancel = onCancelConversion,
            onSave = onSaveConversion,
            onDismissError = onDismissConversionError,
        )
        AppRoute.COVER_SETUP -> CoverSetupScreen(
            state = coverState,
            callbacks = coverCallbacks,
        )
        AppRoute.COVER_EDITOR -> Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Text("封面編輯器準備中")
        }
    }
}
