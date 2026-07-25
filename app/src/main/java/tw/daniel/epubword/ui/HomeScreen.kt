package tw.daniel.epubword.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun HomeScreen(
    onOpenConverter: () -> Unit,
    onOpenCover: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "EPUB／Word 排版與封面工具",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
        )
        Text("所有文件處理都在裝置本機完成。")
        Button(
            onClick = onOpenConverter,
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
        ) {
            Text("轉換 EPUB／Word")
        }
        OutlinedButton(
            onClick = onOpenCover,
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
        ) {
            Text("封面工具")
        }
    }
}
