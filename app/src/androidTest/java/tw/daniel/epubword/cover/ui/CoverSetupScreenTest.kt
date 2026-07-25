package tw.daniel.epubword.cover.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsOff
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test
import tw.daniel.epubword.ui.theme.EpubWordTheme

class CoverSetupScreenTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun estimatedPagesRequireConfirmationAndShowSpine() {
        compose.setContent {
            EpubWordTheme {
                CoverSetupScreen(
                    state = CoverUiState(
                        status = CoverStatus.SETUP,
                        sourceName = "book.epub",
                        sourcePath = "/tmp/book.epub",
                        pageCount = 160,
                        pageCountEstimated = true,
                        pageCountConfirmed = false,
                    ),
                    callbacks = CoverSetupCallbacks(),
                )
            }
        }

        compose.onNodeWithText("頁數為估算值").assertIsDisplayed()
        compose.onNodeWithText("我已確認正文頁數").assertIsOff()
        compose.onNodeWithText("自動書脊：8.0 mm").assertIsDisplayed()
        compose.onNodeWithText("建立封面").assertIsNotEnabled()
    }
}
