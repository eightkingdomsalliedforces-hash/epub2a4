package tw.daniel.epubword.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import tw.daniel.epubword.model.MarginMode
import tw.daniel.epubword.model.OutputMode

enum class AppRoute { HOME, CONVERTER, COVER_SETUP, COVER_EDITOR }

data class CoverHandoffToken(val value: String)

data class AppRouteState(
    val route: AppRoute = AppRoute.HOME,
    val coverHandoff: CoverHandoffToken? = null,
) {
    fun navigate(
        next: AppRoute,
        handoff: CoverHandoffToken? = coverHandoff,
    ): AppRouteState = copy(route = next, coverHandoff = handoff)
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
    onChooseCoverSource: () -> Unit,
    onChooseCoverImage: () -> Unit,
    onChooseCoverDirectory: () -> Unit,
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
        AppRoute.COVER_SETUP -> Column(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("封面工具")
            Text("選擇 EPUB、DOCX 或 PDF，下一步確認實體書尺寸與頁數。")
            Button(
                onClick = onChooseCoverSource,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("選擇封面來源")
            }
        }
        AppRoute.COVER_EDITOR -> Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Text("封面編輯器準備中")
        }
    }

    // Launchers are owned by MainActivity. Later cover screens consume these callbacks
    // without moving SAF or business logic into the activity.
    @Suppress("UNUSED_VARIABLE")
    val deferredCoverCallbacks = onChooseCoverImage to onChooseCoverDirectory
}
