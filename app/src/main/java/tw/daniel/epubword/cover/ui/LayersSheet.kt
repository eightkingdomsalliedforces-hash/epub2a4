package tw.daniel.epubword.cover.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import tw.daniel.epubword.cover.model.CoverElement

@Composable
fun LayersSheet(
    elements: List<CoverElement>,
    selectedElementId: String?,
    onSelect: (String) -> Unit,
    onDelete: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.navigationBarsPadding().padding(16.dp)) {
        Text("圖層", style = MaterialTheme.typography.titleLarge)
        if (elements.isEmpty()) {
            Text("目前沒有可編輯元素。", modifier = Modifier.padding(vertical = 16.dp))
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            items(elements.sortedByDescending { it.zIndex }, key = { it.id }) { element ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onSelect(element.id) }
                        .padding(vertical = 10.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            element.content.optString("text").ifBlank {
                                element.content.optString("path").substringAfterLast('/').ifBlank {
                                    element.kind.wire
                                }
                            },
                            color = if (element.id == selectedElementId) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.onSurface
                            },
                        )
                        Text("${element.region.wire} · z ${element.zIndex}")
                    }
                    TextButton(onClick = { onDelete(element.id) }) { Text("刪除") }
                }
            }
        }
    }
}
