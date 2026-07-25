package tw.daniel.epubword.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test
import tw.daniel.epubword.ui.theme.EpubWordTheme

class AppRootTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun homeOffersConverterAndCoverTools() {
        compose.setContent { EpubWordTheme { HomeScreen({}, {}) } }
        compose.onNodeWithText("轉換 EPUB／Word").assertIsDisplayed()
        compose.onNodeWithText("封面工具").assertIsDisplayed()
    }
}
