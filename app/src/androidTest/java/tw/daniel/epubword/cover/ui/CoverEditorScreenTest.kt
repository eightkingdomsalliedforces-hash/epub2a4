package tw.daniel.epubword.cover.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test
import tw.daniel.epubword.ui.theme.EpubWordTheme

class CoverEditorScreenTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun editorShowsCoreActions() {
        compose.setContent {
            EpubWordTheme {
                CoverEditorScreen(
                    state = CoverUiState(status = CoverStatus.EDITING),
                    callbacks = CoverEditorCallbacks(),
                )
            }
        }

        compose.onNodeWithContentDescription("復原").assertIsDisplayed()
        compose.onNodeWithContentDescription("重做").assertIsDisplayed()
        compose.onNodeWithText("加入圖片").assertIsDisplayed()
        compose.onNodeWithText("加入文字").assertIsDisplayed()
        compose.onNodeWithText("圖層").assertIsDisplayed()
        compose.onNodeWithText("匯出").assertIsDisplayed()
    }
}
