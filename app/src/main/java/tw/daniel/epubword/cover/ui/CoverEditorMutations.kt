package tw.daniel.epubword.cover.ui

import androidx.compose.ui.geometry.Offset
import org.json.JSONObject
import tw.daniel.epubword.cover.model.CoverElement
import tw.daniel.epubword.cover.model.CoverProject
import tw.daniel.epubword.cover.model.CoverRegion
import tw.daniel.epubword.cover.model.ElementKind
import tw.daniel.epubword.cover.model.ElementTransform
import java.io.File
import java.util.ArrayDeque
import java.util.UUID
import kotlin.math.max

internal class CoverEditHistory(private val limit: Int = 50) {
    private val undo = ArrayDeque<String>()
    private val redo = ArrayDeque<String>()

    init {
        require(limit > 0)
    }

    val canUndo: Boolean get() = undo.isNotEmpty()
    val canRedo: Boolean get() = redo.isNotEmpty()

    fun clear() {
        undo.clear()
        redo.clear()
    }

    fun record(currentJson: String) {
        if (currentJson.isBlank()) return
        if (undo.peekLast() != currentJson) undo.addLast(currentJson)
        while (undo.size > limit) undo.removeFirst()
        redo.clear()
    }

    fun undo(currentJson: String): String? {
        if (undo.isEmpty()) return null
        if (currentJson.isNotBlank()) {
            redo.addLast(currentJson)
            while (redo.size > limit) redo.removeFirst()
        }
        return undo.removeLast()
    }

    fun redo(currentJson: String): String? {
        if (redo.isEmpty()) return null
        if (currentJson.isNotBlank()) {
            undo.addLast(currentJson)
            while (undo.size > limit) undo.removeFirst()
        }
        return redo.removeLast()
    }
}

internal fun CoverProject.patchElement(id: String, patch: ElementPatch): CoverProject {
    var found = false
    val updated = elements.map { element ->
        if (element.id != id) return@map element
        found = true
        element.copy(
            transform = patch.transform ?: element.transform,
            opacity = patch.opacity ?: element.opacity,
            content = patch.content?.let { JSONObject(it.toString()) }
                ?: JSONObject(element.content.toString()),
        )
    }
    require(found) { "找不到封面元素：$id" }
    return copy(elements = updated)
}

internal fun CoverProject.applyTransformPatch(patch: ElementTransformPatch): CoverProject {
    val element = elements.firstOrNull { it.id == patch.elementId }
        ?: throw IllegalArgumentException("找不到封面元素：${patch.elementId}")
    require(patch.scale.isFinite() && patch.scale > 0.0) { "縮放比例必須大於 0。" }
    val transform = element.transform
    return patchElement(
        patch.elementId,
        ElementPatch(
            transform = transform.copy(
                xMm = transform.xMm + patch.deltaXMm,
                yMm = transform.yMm + patch.deltaYMm,
                widthMm = transform.widthMm * patch.scale,
                heightMm = transform.heightMm * patch.scale,
                rotationDeg = transform.rotationDeg + patch.rotationDeltaDeg,
            ),
        ),
    )
}

internal fun CoverProject.removeElement(id: String): CoverProject {
    val updated = elements.filterNot { it.id == id }
    require(updated.size != elements.size) { "找不到封面元素：$id" }
    return copy(elements = updated)
}

internal fun CoverProject.addTextElement(): Pair<CoverProject, String> {
    val id = "android-text-${UUID.randomUUID()}"
    val frontX = bleedMm + trimSize.widthMm + spineWidthMm()
    val width = max(20.0, trimSize.widthMm - 20.0)
    val element = CoverElement(
        id = id,
        kind = ElementKind.TEXT,
        region = CoverRegion.FRONT,
        transform = ElementTransform(
            xMm = frontX + 10.0,
            yMm = bleedMm + trimSize.heightMm * 0.38,
            widthMm = width,
            heightMm = 24.0,
        ),
        zIndex = (elements.maxOfOrNull(CoverElement::zIndex) ?: 0) + 1,
        opacity = 1.0,
        content = JSONObject()
            .put("text", "新增文字")
            .put("font_family", "sans-serif")
            .put("font_size_pt", 20.0)
            .put("color", "#111111")
            .put("align", "center")
            .put("line_spacing", 1.15),
    )
    return copy(elements = elements + element) to id
}

internal fun CoverProject.addImageElement(image: File): Pair<CoverProject, String> {
    require(image.isFile && image.length() > 0L) { "找不到匯入的圖片。" }
    val id = "android-image-${UUID.randomUUID()}"
    val spine = spineWidthMm()
    val region = if (imageMode.wire == "full_spread") CoverRegion.SPREAD else CoverRegion.FRONT
    val transform = if (region == CoverRegion.SPREAD) {
        ElementTransform(
            xMm = 0.0,
            yMm = 0.0,
            widthMm = 2.0 * trimSize.widthMm + spine + 2.0 * bleedMm,
            heightMm = trimSize.heightMm + 2.0 * bleedMm,
        )
    } else {
        ElementTransform(
            xMm = bleedMm + trimSize.widthMm + spine,
            yMm = bleedMm,
            widthMm = trimSize.widthMm,
            heightMm = trimSize.heightMm,
        )
    }
    val element = CoverElement(
        id = id,
        kind = ElementKind.IMAGE,
        region = region,
        transform = transform,
        zIndex = (elements.maxOfOrNull(CoverElement::zIndex) ?: 0) + 1,
        opacity = 1.0,
        content = JSONObject()
            .put("path", image.absolutePath)
            .put("fit", "cover"),
    )
    return copy(elements = elements + element) to id
}

internal fun CoverProject.topmostElementAt(pointMm: Offset): String? = elements
    .asSequence()
    .filter { element ->
        val transform = element.transform
        pointMm.x.toDouble() in transform.xMm..(transform.xMm + transform.widthMm) &&
            pointMm.y.toDouble() in transform.yMm..(transform.yMm + transform.heightMm)
    }
    .maxByOrNull(CoverElement::zIndex)
    ?.id

internal fun CoverProject.editorGuides(): CoverGuides {
    val spine = spineWidthMm()
    val back = MmRect(bleedMm, bleedMm, trimSize.widthMm, trimSize.heightMm)
    val spineRect = MmRect(
        bleedMm + trimSize.widthMm,
        bleedMm,
        spine,
        trimSize.heightMm,
    )
    val front = MmRect(
        bleedMm + trimSize.widthMm + spine,
        bleedMm,
        trimSize.widthMm,
        trimSize.heightMm,
    )
    val safeInset = 5.0
    val safe = listOf(back, front).map { rect ->
        MmRect(
            xMm = rect.xMm + safeInset,
            yMm = rect.yMm + safeInset,
            widthMm = (rect.widthMm - safeInset * 2).coerceAtLeast(0.0),
            heightMm = (rect.heightMm - safeInset * 2).coerceAtLeast(0.0),
        )
    }
    val spreadWidth = 2.0 * trimSize.widthMm + spine + 2.0 * bleedMm
    val spreadHeight = trimSize.heightMm + 2.0 * bleedMm
    val a4 = buildList {
        var x = 0.0
        while (x < spreadWidth) {
            add(MmRect(x, 0.0, minOf(210.0, spreadWidth - x), minOf(297.0, spreadHeight)))
            x += 210.0
        }
    }
    return CoverGuides(
        regionRects = listOf(back, spineRect, front),
        safeRects = safe,
        bleedRects = listOf(MmRect(0.0, 0.0, spreadWidth, spreadHeight)),
        a4Rects = a4,
    )
}

internal fun CoverProject.spineWidthMm(): Double =
    manualSpineWidthMm ?: ((pageCount + 1) / 2) * paperCaliperMm
