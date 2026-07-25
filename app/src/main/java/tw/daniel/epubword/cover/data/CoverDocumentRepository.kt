package tw.daniel.epubword.cover.data

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID

const val DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
private const val PDF_MIME = "application/pdf"
private const val EPUB_MIME = "application/epub+zip"
private const val MAX_SOURCE_BYTES = 500L * 1024L * 1024L
private const val MAX_IMAGE_BYTES = 50L * 1024L * 1024L
private const val COPY_BUFFER_BYTES = 1024 * 1024

enum class CoverInputKind(val extension: String) {
    EPUB("epub"),
    DOCX("docx"),
    PDF("pdf"),
}

fun kindFor(fileName: String, mimeType: String?): CoverInputKind {
    val extensionKind = when (fileName.substringAfterLast('.', "").lowercase()) {
        "epub" -> CoverInputKind.EPUB
        "docx" -> CoverInputKind.DOCX
        "pdf" -> CoverInputKind.PDF
        else -> null
    }
    val mimeKind = when (mimeType?.lowercase()) {
        EPUB_MIME -> CoverInputKind.EPUB
        DOCX_MIME -> CoverInputKind.DOCX
        PDF_MIME -> CoverInputKind.PDF
        else -> null
    }
    return extensionKind ?: mimeKind
        ?: throw IllegalArgumentException("封面來源只支援 EPUB、DOCX 或 PDF。")
}

fun coverExportName(title: String, extension: String): String {
    val normalizedExtension = extension.lowercase().removePrefix(".")
    require(normalizedExtension == "pdf" || normalizedExtension == "docx") {
        "封面輸出只支援 PDF 或 DOCX。"
    }
    val safeTitle = title
        .replace(Regex("[\\/:*?\"<>|\\p{Cntrl}]"), "_")
        .trim()
        .trim('_', '.')
        .take(120)
        .ifBlank { "書籍" }
    return "${safeTitle}_完整書封.$normalizedExtension"
}

data class SavedCoverFiles(
    val pdfUri: Uri?,
    val docxUri: Uri?,
    val errorMessage: String? = null,
    val pdfSaved: Boolean = pdfUri != null,
    val docxSaved: Boolean = docxUri != null,
) {
    val isComplete: Boolean get() = pdfSaved && docxSaved && errorMessage == null

    val userMessage: String get() = when {
        pdfSaved && docxSaved -> "PDF 與 DOCX 已儲存。"
        pdfSaved -> "PDF 已儲存；DOCX 儲存失敗，可重試。"
        docxSaved -> "DOCX 已儲存；PDF 儲存失敗，可重試。"
        else -> errorMessage ?: "PDF 與 DOCX 尚未儲存。"
    }
}

class CoverDocumentRepository(private val context: Context) {
    private val resolver: ContentResolver = context.contentResolver
    private var activeFiles: CoverWorkingFiles? = null

    suspend fun stageSource(uri: Uri): StagedCoverSource = withContext(Dispatchers.IO) {
        val displayName = queryDisplayName(uri) ?: "document"
        val kind = kindFor(displayName, resolver.getType(uri))
        val session = createSession()
        val normalizedName = ensureExtension(displayName, kind.extension)
        val destination = File(session.sourceDir, safeFileName(normalizedName))
        try {
            val copied = copyUri(uri, destination, MAX_SOURCE_BYTES)
            activeFiles?.root?.takeIf { it != session.root }?.deleteRecursively()
            activeFiles = session
            StagedCoverSource(destination, normalizedName, kind, copied, session)
        } catch (failure: Throwable) {
            session.root.deleteRecursively()
            throw failure
        }
    }

    suspend fun stageLocalImage(uri: Uri): File = withContext(Dispatchers.IO) {
        val session = requireActiveSession()
        val displayName = queryDisplayName(uri) ?: "cover-image"
        val destination = File(
            session.assetsDir,
            "${UUID.randomUUID()}-${safeFileName(displayName)}",
        )
        copyUri(uri, destination, MAX_IMAGE_BYTES)
        destination
    }

    fun createPreviewFile(): File = File(
        requireActiveSession().previewDir,
        "preview-${UUID.randomUUID()}.png",
    )

    fun createPdfFile(title: String): File = File(
        requireActiveSession().exportDir,
        coverExportName(title, "pdf"),
    )

    fun createDocxFile(title: String): File = File(
        requireActiveSession().exportDir,
        coverExportName(title, "docx"),
    )

    suspend fun saveExportPair(
        pdf: File,
        docx: File,
        treeUri: Uri,
        title: String,
    ): SavedCoverFiles = withContext(Dispatchers.IO) {
        require(pdf.isFile && pdf.length() > 0L) { "找不到待儲存的 PDF 封面。" }
        require(docx.isFile && docx.length() > 0L) { "找不到待儲存的 DOCX 封面。" }
        val rootDocumentId = DocumentsContract.getTreeDocumentId(treeUri)
        val rootUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, rootDocumentId)
        val pdfUri = createAndCopy(
            rootUri,
            PDF_MIME,
            coverExportName(title, "pdf"),
            pdf,
        )
        try {
            val docxUri = createAndCopy(
                rootUri,
                DOCX_MIME,
                coverExportName(title, "docx"),
                docx,
            )
            SavedCoverFiles(pdfUri = pdfUri, docxUri = docxUri)
        } catch (failure: Throwable) {
            SavedCoverFiles(
                pdfUri = pdfUri,
                docxUri = null,
                errorMessage = failure.message ?: "DOCX 儲存失敗。",
                pdfSaved = true,
                docxSaved = false,
            )
        }
    }

    fun clearSession(keepForRetry: Boolean = false) {
        if (!keepForRetry) {
            activeFiles?.root?.deleteRecursively()
            activeFiles = null
        }
    }

    private fun createSession(): CoverWorkingFiles {
        val root = File(context.cacheDir, "cover/${UUID.randomUUID()}")
        return CoverWorkingFiles(
            root = root,
            sourceDir = File(root, "source").apply(File::mkdirs),
            assetsDir = File(root, "assets").apply(File::mkdirs),
            previewDir = File(root, "preview").apply(File::mkdirs),
            exportDir = File(root, "export").apply(File::mkdirs),
        )
    }

    private fun copyUri(uri: Uri, destination: File, maxBytes: Long): Long {
        destination.parentFile?.mkdirs()
        val temporary = File(destination.parentFile, destination.name + ".part")
        temporary.delete()
        var copied = 0L
        try {
            resolver.openInputStream(uri).use { input ->
                requireNotNull(input) { "無法開啟所選檔案。" }
                temporary.outputStream().buffered(COPY_BUFFER_BYTES).use { output ->
                    val buffer = ByteArray(COPY_BUFFER_BYTES)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        copied += count
                        require(copied <= maxBytes) { "檔案超過允許大小。" }
                        output.write(buffer, 0, count)
                    }
                }
            }
            require(copied > 0L) { "檔案內容是空的。" }
            if (destination.exists()) destination.delete()
            check(temporary.renameTo(destination)) { "無法完成工作檔案寫入。" }
            return copied
        } catch (failure: Throwable) {
            temporary.delete()
            destination.delete()
            throw failure
        }
    }

    private fun createAndCopy(parent: Uri, mime: String, name: String, source: File): Uri {
        val destination = requireNotNull(
            DocumentsContract.createDocument(resolver, parent, mime, name),
        ) { "無法建立 $name。" }
        resolver.openOutputStream(destination, "w").use { output ->
            requireNotNull(output) { "無法寫入 $name。" }
            source.inputStream().buffered(COPY_BUFFER_BYTES).use { input ->
                input.copyTo(output, COPY_BUFFER_BYTES)
            }
        }
        return destination
    }

    private fun queryDisplayName(uri: Uri): String? = resolver.query(
        uri,
        arrayOf(OpenableColumns.DISPLAY_NAME),
        null,
        null,
        null,
    )?.use { cursor ->
        val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (index >= 0 && cursor.moveToFirst()) cursor.getString(index) else null
    }

    private fun requireActiveSession(): CoverWorkingFiles =
        requireNotNull(activeFiles) { "尚未建立封面工作階段。" }

    private fun ensureExtension(name: String, extension: String): String =
        if (name.endsWith(".$extension", ignoreCase = true)) name else "$name.$extension"

    private fun safeFileName(value: String): String = value
        .replace(Regex("[\\/:*?\"<>|\\p{Cntrl}]"), "_")
        .trim()
        .take(160)
        .ifBlank { "document" }
}
