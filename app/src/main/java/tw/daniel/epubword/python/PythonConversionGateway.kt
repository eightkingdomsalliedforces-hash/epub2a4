package tw.daniel.epubword.python

import android.content.Context
import com.chaquo.python.PyException
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import tw.daniel.epubword.model.ConversionOptions
import tw.daniel.epubword.model.ConversionResult
import java.io.File
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicBoolean

class PythonConversionGateway(
    context: Context,
    private val executor: LargeStackPythonExecutor = LargeStackPythonExecutor(),
) : AutoCloseable {
    private val appContext = context.applicationContext

    suspend fun convert(
        input: File,
        output: File,
        options: ConversionOptions,
        cancellation: AtomicBoolean,
        onProgress: (Int, String) -> Unit,
    ): ConversionResult = executor.runSuspending {
        convertBlocking(input, output, options, cancellation, onProgress)
    }

    private fun convertBlocking(
        input: File,
        output: File,
        options: ConversionOptions,
        cancellation: AtomicBoolean,
        onProgress: (Int, String) -> Unit,
    ): ConversionResult {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(appContext))
        }
        val proxy = ProgressProxy(cancellation, onProgress)
        try {
            val payload = Python.getInstance()
                .getModule("android_bridge")
                .callAttr(
                    "convert_file_json",
                    input.absolutePath,
                    output.absolutePath,
                    options.toJson(),
                    proxy,
                )
                .toString()
            return parseResult(payload)
        } catch (exception: PyException) {
            if (cancellation.get() || exception.message.orEmpty().contains("ConversionCancelled")) {
                throw CancellationException("轉換已取消。")
            }
            throw ConversionFailure(classifyError(exception.message.orEmpty()), exception)
        }
    }

    override fun close() {
        executor.close()
    }

    private fun parseResult(payload: String): ConversionResult {
        val json = JSONObject(payload)
        val warningsJson = json.optJSONArray("warnings")
        val warnings = buildList {
            if (warningsJson != null) {
                for (index in 0 until warningsJson.length()) add(warningsJson.optString(index))
            }
        }
        return ConversionResult(
            outputPath = json.getString("output_path"),
            title = json.optString("title"),
            author = json.optString("author"),
            miniPageCount = json.optInt("mini_page_count"),
            printSideCount = json.optInt("a4_page_count"),
            imageCount = json.optInt("image_count"),
            warnings = warnings,
            outputMode = json.optString("imposition_mode"),
            paperSheetCount = json.optInt("paper_sheet_count"),
            signatureCount = json.optInt("signature_count"),
            paddedMiniPageCount = json.optInt("padded_mini_page_count"),
            sourceFormat = json.optString("source_format"),
        )
    }

    private fun classifyError(message: String): String = when {
        message.contains("EPUB", ignoreCase = true) -> "EPUB 解析失敗：${cleanMessage(message)}"
        message.contains("DOCX", ignoreCase = true) || message.contains("Word", ignoreCase = true) ->
            "Word 重新排版失敗：${cleanMessage(message)}"
        message.contains("No space", ignoreCase = true) -> "手機儲存空間不足。"
        else -> "轉換失敗：${cleanMessage(message)}"
    }

    private fun cleanMessage(message: String): String = message
        .lineSequence()
        .lastOrNull { it.isNotBlank() }
        ?.substringAfter(':')
        ?.trim()
        .orEmpty()
        .ifBlank { "未知錯誤" }

    class ProgressProxy(
        private val cancellation: AtomicBoolean,
        private val progressCallback: (Int, String) -> Unit,
    ) {
        @Suppress("unused")
        fun onProgress(percent: Int, message: String) {
            progressCallback(percent.coerceIn(0, 100), message)
        }

        @Suppress("unused")
        fun isCancelled(): Boolean = cancellation.get()
    }
}

class ConversionFailure(message: String, cause: Throwable? = null) : RuntimeException(message, cause)
