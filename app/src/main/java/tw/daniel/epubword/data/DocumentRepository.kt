package tw.daniel.epubword.data

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import tw.daniel.epubword.model.InputKind
import tw.daniel.epubword.model.OutputMode
import tw.daniel.epubword.model.StagedInput
import java.io.File
import java.io.FileNotFoundException
import java.util.UUID

class DocumentRepository(private val context: Context) {
    private val resolver: ContentResolver = context.contentResolver
    private val workRoot = File(context.cacheDir, "conversion-work")

    suspend fun stageInput(uri: Uri): StagedInput = withContext(Dispatchers.IO) {
        val displayName = queryDisplayName(uri) ?: "document"
        val kind = InputKind.fromFileName(displayName) ?: kindFromMimeType(resolver.getType(uri))
            ?: throw IllegalArgumentException("請選擇 EPUB 或 DOCX 文件。")
        val normalizedName = ensureExtension(displayName, kind.extension)
        val directory = File(workRoot, "input").apply { mkdirs() }
        val localFile = File(directory, "${UUID.randomUUID()}-${safeFileName(normalizedName)}")

        resolver.openInputStream(uri)?.use { input ->
            localFile.outputStream().buffered().use { output -> input.copyTo(output) }
        } ?: throw FileNotFoundException("無法讀取所選文件。")

        if (localFile.length() == 0L) {
            localFile.delete()
            throw IllegalArgumentException("所選文件是空的。")
        }
        StagedInput(localFile = localFile, displayName = normalizedName, kind = kind, sizeBytes = localFile.length())
    }

    fun createOutputFile(input: StagedInput, mode: OutputMode): File {
        val directory = File(workRoot, "output").apply { mkdirs() }
        val stem = input.displayName.substringBeforeLast('.', input.displayName)
        return File(directory, "${safeFileName(stem)}_${mode.fileSuffix}_${UUID.randomUUID()}.docx")
    }

    fun suggestedOutputName(input: StagedInput, mode: OutputMode): String {
        val stem = input.displayName.substringBeforeLast('.', input.displayName)
        return "${safeFileName(stem)}_${mode.fileSuffix}.docx"
    }

    suspend fun saveOutput(localFile: File, destination: Uri) = withContext(Dispatchers.IO) {
        require(localFile.isFile) { "找不到待儲存的轉換結果。" }
        resolver.openOutputStream(destination, "w")?.use { output ->
            localFile.inputStream().buffered().use { input -> input.copyTo(output) }
        } ?: throw FileNotFoundException("無法開啟所選儲存位置。")
    }

    fun delete(file: File?) {
        if (file?.isFile == true) file.delete()
    }

    fun clearWorkingFiles() {
        workRoot.deleteRecursively()
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

    private fun kindFromMimeType(mimeType: String?): InputKind? = when (mimeType) {
        "application/epub+zip" -> InputKind.EPUB
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document" -> InputKind.DOCX
        else -> null
    }

    private fun ensureExtension(name: String, extension: String): String =
        if (name.endsWith(".$extension", ignoreCase = true)) name else "$name.$extension"

    private fun safeFileName(value: String): String = value
        .replace(Regex("[\\\\/:*?\"<>|\\p{Cntrl}]"), "_")
        .trim()
        .take(120)
        .ifBlank { "document" }
}
