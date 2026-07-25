package tw.daniel.epubword.cover.data

import java.io.File

data class CoverWorkingFiles(
    val root: File,
    val sourceDir: File,
    val assetsDir: File,
    val previewDir: File,
    val exportDir: File,
)

data class StagedCoverSource(
    val localFile: File,
    val displayName: String,
    val kind: CoverInputKind,
    val sizeBytes: Long,
    val workingFiles: CoverWorkingFiles,
)
