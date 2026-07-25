package tw.daniel.epubword.cover.ui

import androidx.compose.foundation.layout.size
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.unit.dp
import org.junit.Rule
import org.junit.Test
import tw.daniel.epubword.ui.theme.EpubWordTheme

class CoverEditorCanvasTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun displaysRenderedPreview() {
        compose.setContent {
            EpubWordTheme {
                CoverEditorCanvas(
                    bitmap = ImageBitmap(20, 20),
                    viewport = CoverViewport(scalePxPerMm = 1.0),
                    guides = CoverGuides(),
                    selected = null,
                    modifier = Modifier.size(240.dp),
                )
            }
        }

        compose.onNodeWithContentDescription("封面預覽").assertIsDisplayed()
    }
}
