package tw.daniel.epubword.cover.ui

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import tw.daniel.epubword.cover.model.ElementTransform
import kotlin.math.min

data class CoverViewport(
    val scalePxPerMm: Double,
    val offsetPx: Offset = Offset.Zero,
) {
    val zoomFactor: Double get() = scalePxPerMm

    fun normalized(): CoverViewport = copy(
        scalePxPerMm = scalePxPerMm.coerceIn(MIN_SCALE, MAX_SCALE),
    )

    fun mmToScreen(point: Offset): Offset = Offset(
        x = offsetPx.x + point.x * scalePxPerMm.toFloat(),
        y = offsetPx.y + point.y * scalePxPerMm.toFloat(),
    )

    fun screenToMm(point: Offset): Offset = Offset(
        x = (point.x - offsetPx.x) / scalePxPerMm.toFloat(),
        y = (point.y - offsetPx.y) / scalePxPerMm.toFloat(),
    )

    fun pxToMm(value: Float): Double = value / scalePxPerMm

    fun applyGesture(panPx: Offset, zoom: Float): CoverViewport = copy(
        scalePxPerMm = scalePxPerMm * zoom.toDouble(),
        offsetPx = offsetPx + panPx,
    ).normalized()

    companion object {
        const val MIN_SCALE = 0.1
        const val MAX_SCALE = 8.0
    }
}

fun fitScalePxPerMm(
    availableWidthPx: Float,
    availableHeightPx: Float,
    canvasWidthMm: Double,
    canvasHeightMm: Double,
): Double {
    require(availableWidthPx > 0f && availableHeightPx > 0f) {
        "可用畫布尺寸必須大於 0。"
    }
    require(canvasWidthMm > 0.0 && canvasHeightMm > 0.0) {
        "封面毫米尺寸必須大於 0。"
    }
    return min(
        availableWidthPx / canvasWidthMm,
        availableHeightPx / canvasHeightMm,
    ) * 0.92
}

data class MmRect(
    val xMm: Double,
    val yMm: Double,
    val widthMm: Double,
    val heightMm: Double,
) {
    init {
        require(widthMm >= 0.0 && heightMm >= 0.0)
    }

    val topLeft: Offset get() = Offset(xMm.toFloat(), yMm.toFloat())
    val size: Size get() = Size(widthMm.toFloat(), heightMm.toFloat())
}

data class CoverGuides(
    val regionRects: List<MmRect> = emptyList(),
    val safeRects: List<MmRect> = emptyList(),
    val bleedRects: List<MmRect> = emptyList(),
    val a4Rects: List<MmRect> = emptyList(),
)

data class ElementTransformPatch(
    val elementId: String,
    val deltaXMm: Double = 0.0,
    val deltaYMm: Double = 0.0,
    val scale: Double = 1.0,
    val rotationDeltaDeg: Double = 0.0,
)

fun ElementTransform.toMmRect(): MmRect = MmRect(
    xMm = xMm,
    yMm = yMm,
    widthMm = widthMm,
    heightMm = heightMm,
)
