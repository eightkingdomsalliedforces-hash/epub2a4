package tw.daniel.epubword.cover.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateRotation
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChanged
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import tw.daniel.epubword.cover.model.ElementTransform
import kotlin.math.roundToInt

@Composable
fun CoverEditorCanvas(
    bitmap: ImageBitmap,
    viewport: CoverViewport,
    guides: CoverGuides,
    selected: ElementTransform?,
    modifier: Modifier = Modifier,
    selectedElementId: String? = null,
    canvasWidthMm: Double = bitmap.width.toDouble(),
    canvasHeightMm: Double = bitmap.height.toDouble(),
    onCommitTransform: (ElementTransformPatch) -> Unit = {},
    onCommitViewport: (CoverViewport) -> Unit = {},
    onLongPressMm: (Offset) -> Unit = {},
) {
    val normalizedViewport = viewport.normalized()
    Box(
        modifier = modifier
            .clipToBounds()
            .background(Color(0xFFD1D5DB))
            .pointerInput(selectedElementId, normalizedViewport) {
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    var accumulatedPan = Offset.Zero
                    var accumulatedZoom = 1f
                    var accumulatedRotation = 0f
                    do {
                        val event = awaitPointerEvent()
                        accumulatedPan += event.calculatePan()
                        accumulatedZoom *= event.calculateZoom()
                        accumulatedRotation += event.calculateRotation()
                        event.changes.forEach { change ->
                            if (change.positionChanged()) change.consume()
                        }
                    } while (event.changes.any { it.pressed })

                    if (selectedElementId != null) {
                        onCommitTransform(
                            ElementTransformPatch(
                                elementId = selectedElementId,
                                deltaXMm = normalizedViewport.pxToMm(accumulatedPan.x),
                                deltaYMm = normalizedViewport.pxToMm(accumulatedPan.y),
                                scale = accumulatedZoom.toDouble(),
                                rotationDeltaDeg = accumulatedRotation.toDouble(),
                            ),
                        )
                    } else {
                        onCommitViewport(
                            normalizedViewport.applyGesture(
                                panPx = accumulatedPan,
                                zoom = accumulatedZoom,
                            ),
                        )
                    }
                }
            }
            .pointerInput(normalizedViewport) {
                detectTapGestures(
                    onLongPress = { position ->
                        onLongPressMm(normalizedViewport.screenToMm(position))
                    },
                )
            },
    ) {
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .semantics { contentDescription = "封面預覽" },
        ) {
            val previewWidthPx = canvasWidthMm * normalizedViewport.scalePxPerMm
            val previewHeightPx = canvasHeightMm * normalizedViewport.scalePxPerMm
            drawImage(
                image = bitmap,
                dstOffset = IntOffset(
                    normalizedViewport.offsetPx.x.roundToInt(),
                    normalizedViewport.offsetPx.y.roundToInt(),
                ),
                dstSize = IntSize(
                    previewWidthPx.roundToInt().coerceAtLeast(1),
                    previewHeightPx.roundToInt().coerceAtLeast(1),
                ),
            )

            fun drawGuide(rect: MmRect, color: Color, width: Float = 1.5f) {
                val topLeft = normalizedViewport.mmToScreen(rect.topLeft)
                drawRect(
                    color = color,
                    topLeft = topLeft,
                    size = Size(
                        width = (rect.widthMm * normalizedViewport.scalePxPerMm).toFloat(),
                        height = (rect.heightMm * normalizedViewport.scalePxPerMm).toFloat(),
                    ),
                    style = Stroke(width = width),
                )
            }

            guides.bleedRects.forEach { drawGuide(it, Color(0xFFFF9800)) }
            guides.regionRects.forEach { drawGuide(it, Color(0xFF2563EB)) }
            guides.safeRects.forEach { drawGuide(it, Color(0xFF16A34A)) }
            guides.a4Rects.forEach { drawGuide(it, Color(0xFFC026D3)) }
            selected?.toMmRect()?.let { drawGuide(it, Color(0xFFDC2626), width = 3f) }
        }
    }
}
