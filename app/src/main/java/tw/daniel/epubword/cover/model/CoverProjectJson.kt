package tw.daniel.epubword.cover.model

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

object CoverProjectJson {
    private val rootRequired = setOf(
        "schema_version",
        "source_file",
        "source_type",
        "metadata",
        "trim_size",
        "page_count",
        "paper_caliper_mm",
        "manual_spine_width_mm",
        "bleed_mm",
        "overlap_mm",
        "image_mode",
    )
    private val rootOptional = setOf("working_dir", "background", "elements", "export_settings")

    fun decode(text: String): CoverProject = try {
        decodeProject(JSONObject(text))
    } catch (failure: CoverProjectFormatException) {
        throw failure
    } catch (failure: JSONException) {
        throw CoverProjectFormatException("封面專案 JSON 無效：${failure.message}", failure)
    } catch (failure: RuntimeException) {
        throw CoverProjectFormatException("封面專案格式無效：${failure.message}", failure)
    }

    fun encode(project: CoverProject): String {
        validate(project)
        val root = JSONObject()
            .put("schema_version", project.schemaVersion)
            .put("source_file", project.sourceFile)
            .put("source_type", project.sourceType)
            .put("working_dir", project.workingDir)
            .put("metadata", encodeMetadata(project.metadata))
            .put("trim_size", encodeTrimSize(project.trimSize))
            .put("page_count", project.pageCount)
            .put("paper_caliper_mm", project.paperCaliperMm)
            .put(
                "manual_spine_width_mm",
                project.manualSpineWidthMm ?: JSONObject.NULL,
            )
            .put("bleed_mm", project.bleedMm)
            .put("overlap_mm", project.overlapMm)
            .put("image_mode", project.imageMode.wire)
            .put("background", copyObject(project.background))
            .put("elements", JSONArray().also { array ->
                project.elements.forEach { array.put(encodeElement(it)) }
            })
            .put("export_settings", encodeExportSettings(project.exportSettings))
        return root.toString()
    }

    private fun decodeProject(root: JSONObject): CoverProject {
        requireKeys(root, rootRequired, rootOptional, "root")
        val schemaVersion = integer(root, "schema_version", "schema_version")
        if (schemaVersion != 1) {
            fail("不支援的封面專案版本：$schemaVersion")
        }
        val project = CoverProject(
            schemaVersion = schemaVersion,
            sourceFile = string(root, "source_file", "source_file"),
            sourceType = string(root, "source_type", "source_type"),
            workingDir = optionalString(root, "working_dir", ""),
            metadata = decodeMetadata(root.getJSONObject("metadata")),
            trimSize = decodeTrimSize(root.getJSONObject("trim_size")),
            pageCount = integer(root, "page_count", "page_count"),
            paperCaliperMm = number(root, "paper_caliper_mm", "paper_caliper_mm"),
            manualSpineWidthMm = optionalNumber(root, "manual_spine_width_mm"),
            bleedMm = number(root, "bleed_mm", "bleed_mm"),
            overlapMm = number(root, "overlap_mm", "overlap_mm"),
            imageMode = enumValue(
                ImageMode.entries,
                string(root, "image_mode", "image_mode"),
                "image_mode",
            ) { it.wire },
            background = if (root.has("background")) {
                copyObject(root.getJSONObject("background"))
            } else {
                JSONObject()
            },
            elements = decodeElements(root.optJSONArray("elements") ?: JSONArray()),
            exportSettings = decodeExportSettings(
                root.optJSONObject("export_settings") ?: JSONObject(),
            ),
        )
        validate(project)
        return project
    }

    private fun decodeMetadata(value: JSONObject): CoverMetadata {
        val allowed = setOf(
            "title",
            "author",
            "description",
            "isbn",
            "publisher",
            "price",
            "publication_place",
            "translator",
            "isbn_addon",
            "publisher_id",
            "english_title",
            "volume_number",
            "arc_label",
            "series_name",
            "internal_book_code",
            "spine_accent_color",
            "back_vertical_copy",
            "back_highlight_copy",
            "spine_style",
            "accent_color_mode",
            "extracted_accent_color",
            "language",
            "page_count_is_estimate",
            "embedded_images",
        )
        requireKeys(value, emptySet(), allowed, "metadata")
        val images = value.optJSONArray("embedded_images") ?: JSONArray()
        return CoverMetadata(
            title = optionalString(value, "title", ""),
            author = optionalString(value, "author", ""),
            description = optionalString(value, "description", ""),
            isbn = optionalString(value, "isbn", ""),
            publisher = optionalString(value, "publisher", ""),
            price = optionalString(value, "price", ""),
            publicationPlace = optionalString(value, "publication_place", ""),
            translator = optionalString(value, "translator", ""),
            isbnAddon = optionalString(value, "isbn_addon", ""),
            publisherId = optionalString(value, "publisher_id", ""),
            englishTitle = optionalString(value, "english_title", ""),
            volumeNumber = optionalString(value, "volume_number", ""),
            arcLabel = optionalString(value, "arc_label", ""),
            seriesName = optionalString(value, "series_name", ""),
            internalBookCode = optionalString(value, "internal_book_code", ""),
            spineAccentColor = optionalString(value, "spine_accent_color", "#F15A24"),
            backVerticalCopy = optionalString(value, "back_vertical_copy", ""),
            backHighlightCopy = optionalString(value, "back_highlight_copy", ""),
            spineStyle = optionalString(value, "spine_style", "reference_stacked"),
            accentColorMode = optionalString(value, "accent_color_mode", "auto"),
            extractedAccentColor = optionalString(value, "extracted_accent_color", ""),
            language = optionalString(value, "language", ""),
            pageCountIsEstimate = optionalBoolean(value, "page_count_is_estimate", false),
            embeddedImages = buildList {
                for (index in 0 until images.length()) {
                    val item = images.optJSONObject(index)
                        ?: fail("metadata.embedded_images[$index] 必須是 JSON 物件。")
                    add(copyObject(item))
                }
            },
        )
    }

    private fun decodeTrimSize(value: JSONObject): TrimSize {
        requireKeys(value, setOf("width_mm", "height_mm"), emptySet(), "trim_size")
        return TrimSize(
            widthMm = number(value, "width_mm", "trim_size.width_mm"),
            heightMm = number(value, "height_mm", "trim_size.height_mm"),
        )
    }

    private fun decodeElements(array: JSONArray): List<CoverElement> = buildList {
        for (index in 0 until array.length()) {
            val value = array.optJSONObject(index)
                ?: fail("elements[$index] 必須是 JSON 物件。")
            add(decodeElement(value, index))
        }
    }

    private fun decodeElement(value: JSONObject, index: Int): CoverElement {
        val label = "elements[$index]"
        requireKeys(
            value,
            setOf("id", "kind", "region", "transform"),
            setOf("z_index", "opacity", "content"),
            label,
        )
        return CoverElement(
            id = string(value, "id", "$label.id"),
            kind = enumValue(
                ElementKind.entries,
                string(value, "kind", "$label.kind"),
                "$label.kind",
            ) { it.wire },
            region = enumValue(
                CoverRegion.entries,
                string(value, "region", "$label.region"),
                "$label.region",
            ) { it.wire },
            transform = decodeTransform(value.getJSONObject("transform"), "$label.transform"),
            zIndex = if (value.has("z_index")) {
                integer(value, "z_index", "$label.z_index")
            } else {
                0
            },
            opacity = if (value.has("opacity")) {
                number(value, "opacity", "$label.opacity")
            } else {
                1.0
            },
            content = if (value.has("content")) {
                copyObject(value.getJSONObject("content"))
            } else {
                JSONObject()
            },
        )
    }

    private fun decodeTransform(value: JSONObject, label: String): ElementTransform {
        requireKeys(
            value,
            setOf("x_mm", "y_mm", "width_mm", "height_mm"),
            setOf("rotation_deg"),
            label,
        )
        return ElementTransform(
            xMm = number(value, "x_mm", "$label.x_mm"),
            yMm = number(value, "y_mm", "$label.y_mm"),
            widthMm = number(value, "width_mm", "$label.width_mm"),
            heightMm = number(value, "height_mm", "$label.height_mm"),
            rotationDeg = if (value.has("rotation_deg")) {
                number(value, "rotation_deg", "$label.rotation_deg")
            } else {
                0.0
            },
        )
    }

    private fun decodeExportSettings(value: JSONObject): CoverExportSettings {
        val allowed = setOf("dpi", "show_crop_marks", "show_assembly_marks")
        requireKeys(value, emptySet(), allowed, "export_settings")
        return CoverExportSettings(
            dpi = if (value.has("dpi")) integer(value, "dpi", "export_settings.dpi") else 300,
            showCropMarks = optionalBoolean(value, "show_crop_marks", true),
            showAssemblyMarks = optionalBoolean(value, "show_assembly_marks", true),
        )
    }

    private fun encodeMetadata(value: CoverMetadata): JSONObject = JSONObject()
        .put("title", value.title)
        .put("author", value.author)
        .put("description", value.description)
        .put("isbn", value.isbn)
        .put("publisher", value.publisher)
        .put("price", value.price)
        .put("publication_place", value.publicationPlace)
        .put("translator", value.translator)
        .put("isbn_addon", value.isbnAddon)
        .put("publisher_id", value.publisherId)
        .put("english_title", value.englishTitle)
        .put("volume_number", value.volumeNumber)
        .put("arc_label", value.arcLabel)
        .put("series_name", value.seriesName)
        .put("internal_book_code", value.internalBookCode)
        .put("spine_accent_color", value.spineAccentColor)
        .put("back_vertical_copy", value.backVerticalCopy)
        .put("back_highlight_copy", value.backHighlightCopy)
        .put("spine_style", value.spineStyle)
        .put("accent_color_mode", value.accentColorMode)
        .put("extracted_accent_color", value.extractedAccentColor)
        .put("language", value.language)
        .put("page_count_is_estimate", value.pageCountIsEstimate)
        .put("embedded_images", JSONArray().also { array ->
            value.embeddedImages.forEach { array.put(copyObject(it)) }
        })

    private fun encodeTrimSize(value: TrimSize): JSONObject = JSONObject()
        .put("width_mm", value.widthMm)
        .put("height_mm", value.heightMm)

    private fun encodeElement(value: CoverElement): JSONObject = JSONObject()
        .put("id", value.id)
        .put("kind", value.kind.wire)
        .put("region", value.region.wire)
        .put("transform", JSONObject()
            .put("x_mm", value.transform.xMm)
            .put("y_mm", value.transform.yMm)
            .put("width_mm", value.transform.widthMm)
            .put("height_mm", value.transform.heightMm)
            .put("rotation_deg", value.transform.rotationDeg))
        .put("z_index", value.zIndex)
        .put("opacity", value.opacity)
        .put("content", copyObject(value.content))

    private fun encodeExportSettings(value: CoverExportSettings): JSONObject = JSONObject()
        .put("dpi", value.dpi)
        .put("show_crop_marks", value.showCropMarks)
        .put("show_assembly_marks", value.showAssemblyMarks)

    private fun validate(project: CoverProject) {
        if (project.schemaVersion != 1) fail("不支援的封面專案版本：${project.schemaVersion}")
        if (project.sourceFile.isBlank()) fail("source_file 不可為空。")
        if (project.sourceType.isBlank()) fail("source_type 不可為空。")
        if (project.pageCount <= 0) fail("頁數必須大於 0。")
        positive(project.trimSize.widthMm, "trim_size.width_mm")
        positive(project.trimSize.heightMm, "trim_size.height_mm")
        positive(project.paperCaliperMm, "paper_caliper_mm")
        project.manualSpineWidthMm?.let { positive(it, "manual_spine_width_mm") }
        finite(project.bleedMm, "bleed_mm")
        if (project.bleedMm !in 0.0..10.0) fail("bleed_mm 必須介於 0 與 10。")
        finite(project.overlapMm, "overlap_mm")
        if (project.overlapMm != 5.0) fail("第一版 overlap_mm 必須為 5。")
        if (project.exportSettings.dpi <= 0) fail("export_settings.dpi 必須大於 0。")
        if (project.metadata.spineStyle !in setOf(
                "reference_stacked",
                "clean_centered",
                "parallel_columns",
            )
        ) {
            fail("metadata.spine_style 無效。")
        }
        if (project.metadata.accentColorMode !in setOf("auto", "manual")) {
            fail("metadata.accent_color_mode 無效。")
        }

        val ids = mutableSetOf<String>()
        project.elements.forEach { element ->
            if (element.id.isBlank()) fail("元素 id 不可為空。")
            if (!ids.add(element.id)) fail("封面元素 ID 不可重複：${element.id}")
            finite(element.transform.xMm, "元素 ${element.id} x_mm")
            finite(element.transform.yMm, "元素 ${element.id} y_mm")
            positive(element.transform.widthMm, "元素 ${element.id} width_mm")
            positive(element.transform.heightMm, "元素 ${element.id} height_mm")
            finite(element.transform.rotationDeg, "元素 ${element.id} rotation_deg")
            finite(element.opacity, "元素 ${element.id} opacity")
            if (element.opacity !in 0.0..1.0) {
                fail("元素 ${element.id} 的 opacity 必須介於 0 與 1。")
            }
        }
    }

    private fun requireKeys(
        value: JSONObject,
        required: Set<String>,
        optional: Set<String>,
        label: String,
    ) {
        val keys = buildSet {
            val iterator = value.keys()
            while (iterator.hasNext()) add(iterator.next())
        }
        val missing = required - keys
        if (missing.isNotEmpty()) fail("$label 缺少欄位：${missing.sorted().joinToString("、")}")
        val unknown = keys - required - optional
        if (unknown.isNotEmpty()) fail("$label 包含未知欄位：${unknown.sorted().joinToString("、")}")
    }

    private fun string(value: JSONObject, key: String, label: String): String {
        val raw = value.get(key)
        if (raw !is String) fail("$label 必須是字串。")
        return raw
    }

    private fun optionalString(value: JSONObject, key: String, fallback: String): String =
        if (!value.has(key)) fallback else string(value, key, key)

    private fun number(value: JSONObject, key: String, label: String): Double {
        val raw = value.get(key)
        if (raw !is Number) fail("$label 必須是數字。")
        val result = raw.toDouble()
        finite(result, label)
        return result
    }

    private fun optionalNumber(value: JSONObject, key: String): Double? =
        if (!value.has(key) || value.isNull(key)) null else number(value, key, key)

    private fun integer(value: JSONObject, key: String, label: String): Int {
        val number = number(value, key, label)
        if (number % 1.0 != 0.0 || number < Int.MIN_VALUE || number > Int.MAX_VALUE) {
            fail("$label 必須是整數。")
        }
        return number.toInt()
    }

    private fun optionalBoolean(value: JSONObject, key: String, fallback: Boolean): Boolean {
        if (!value.has(key)) return fallback
        val raw = value.get(key)
        if (raw !is Boolean) fail("$key 必須是布林值。")
        return raw
    }

    private fun <T> enumValue(
        values: Iterable<T>,
        wire: String,
        label: String,
        selector: (T) -> String,
    ): T = values.firstOrNull { selector(it) == wire }
        ?: fail("$label 包含未知值：$wire")

    private fun positive(value: Double, label: String) {
        finite(value, label)
        if (value <= 0.0) fail("$label 必須大於 0。")
    }

    private fun finite(value: Double, label: String) {
        if (!value.isFinite()) fail("$label 必須是有限數字。")
    }

    private fun copyObject(value: JSONObject): JSONObject = JSONObject(value.toString())

    private fun fail(message: String): Nothing = throw CoverProjectFormatException(message)
}
