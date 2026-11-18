package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.ZonedDateTime

/** Ruční volba data v okně úkolu – přebije datum rozpoznané z textu. */
sealed interface DateChoice {
    data object FromText : DateChoice
    data class Fixed(val date: LocalDate?) : DateChoice
}

/** Úkol z prvního řádku textu; ruční volba data má přednost. Používá i náhled v okně zachycení. */
fun parseTaskInput(text: String, now: ZonedDateTime, choice: DateChoice): ParsedTask {
    val parsed = TaskParser.parse(text.trim().lineSequence().first(), now.toLocalDate(), now.toLocalTime())
    return when (choice) {
        DateChoice.FromText -> parsed
        is DateChoice.Fixed -> parsed.copy(date = choice.date, time = choice.date?.let { parsed.time })
    }
}

/** Chyba zápisu – text hlášky dodá okno zachycení v jazyce aplikace. */
class WriteError(val reason: Reason) : IllegalArgumentException(reason.name) {
    enum class Reason { EMPTY, NO_FOLDER, NOT_A_FILE }
}

/** Zapíše zachycený text podle předvolby. Vrací cestu k souboru relativně k vaultu. */
class NoteWriter(
    private val vault: VaultStorage,
    private val tasks: TaskNotesSettings,
    private val daily: DailyNote.Location,
) {
    fun save(
        preset: CapturePreset,
        text: String,
        now: ZonedDateTime,
        choice: DateChoice = DateChoice.FromText,
        project: ProjectRef? = null,
    ): String {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) throw WriteError(WriteError.Reason.EMPTY)
        // Smazaná / přejmenovaná stránka projektu → uložit bez projektu.
        val page = project?.takeIf { vault.exists(it.path) }
        return when (preset.kind) {
            Kind.TASK -> {
                val task = parseTaskInput(trimmed, now, choice).copy(project = page?.name)
                val body = trimmed.lines().drop(1).joinToString("\n")
                val name = FileNameTemplate.render(preset.fileNameTemplate, task.title, preset.label, now)
                newFile(folderOf(preset), name, NoteFormat.task(task, body, now, tasks, preset.tags))
            }
            Kind.NOTE -> when (preset.mode) {
                WriteMode.NEW_FILE -> {
                    val name = FileNameTemplate.render(preset.fileNameTemplate, trimmed.lineSequence().first(), preset.label, now)
                    val path = newFile(folderOf(preset), name, NoteFormat.note(trimmed, preset.tags, now, page?.name))
                    if (page != null) {
                        val link = "- [[" + path.substringAfterLast('/').removeSuffix(".md") + "]]"
                        edit(page.path) { PageEdits.appendToSection(it.orEmpty(), preset.projectSection, link) }
                    }
                    path
                }
                WriteMode.APPEND_END -> edit(targetPath(preset, now)) { appendEnd(it, block(trimmed, now)) }
                WriteMode.APPEND_START -> edit(targetPath(preset, now)) { appendStart(it, block(trimmed, now)) }
                // Ze zástupce do sekce jeho stránky, jinak do souboru předvolby; chybějící sekci založí.
                WriteMode.APPEND_SECTION -> edit(page?.path ?: targetPath(preset, now)) {
                    PageEdits.appendToSection(it.orEmpty(), preset.projectSection, listItem(trimmed))
                }
            }
        }
    }

    /**
     * Připíše [text] na konec souboru [path] (ze zástupce stránky): jako položku seznamu `- [ ] text`
     * (další řádky odsazené pod ní), nebo jako odstavec oddělený prázdným řádkem – jinak by se
     * v Markdownu přilepil k předchozímu odstavci nebo položce.
     */
    fun appendToPage(path: String, text: String, listItem: Boolean): String {
        val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }
        if (lines.isEmpty()) throw WriteError(WriteError.Reason.EMPTY)
        return edit(path) { existing ->
            if (listItem) appendEnd(existing, (listOf("- [ ] " + lines.first()) + lines.drop(1).map { "  $it" }).joinToString("\n"))
            else if (existing.isNullOrBlank()) lines.joinToString("\n") + "\n"
            else existing.trimEnd('\n') + "\n\n" + lines.joinToString("\n") + "\n"
        }
    }

    private fun folderOf(preset: CapturePreset): String =
        (preset.target as? Target.Folder)?.path ?: throw WriteError(WriteError.Reason.NO_FOLDER)

    private fun targetPath(preset: CapturePreset, now: ZonedDateTime): String = when (val t = preset.target) {
        is Target.Note -> t.path
        Target.DailyNote -> DailyNote.path(daily, now.toLocalDate())
        is Target.Folder -> throw WriteError(WriteError.Reason.NOT_A_FILE)
    }

    private fun newFile(folder: String, name: String, content: String): String {
        val dir = folder.trim('/')
        fun path(suffix: String) = (if (dir.isEmpty()) "" else "$dir/") + name + suffix + ".md"
        var candidate = path("")
        var n = 2
        while (vault.exists(candidate)) candidate = path(" ${n++}")
        vault.write(candidate, content)
        return candidate
    }

    /** Čte soubor těsně před zápisem (souběh se Syncthingem); neexistující = null. */
    private fun edit(path: String, change: (String?) -> String): String {
        val existing = if (vault.exists(path)) vault.read(path) else null
        vault.write(path, change(existing))
        return path
    }

    companion object {
        /** `- HH:mm text`; další řádky odsazené pod odrážku, prázdné vynechané. */
        fun block(text: String, now: ZonedDateTime): String {
            val lines = text.lines().map { it.trimEnd() }.filter { it.isNotBlank() }
            val time = "%02d:%02d".format(now.hour, now.minute)
            return (listOf("- $time ${lines.first().trim()}") + lines.drop(1).map { "  ${it.trim()}" }).joinToString("\n")
        }

        /** `- text`; další řádky odsazené pod odrážku, prázdné vynechané. */
        fun listItem(text: String): String {
            val lines = text.lines().map { it.trim() }.filter { it.isNotEmpty() }
            return (listOf("- " + lines.first()) + lines.drop(1).map { "  $it" }).joinToString("\n")
        }

        fun appendEnd(existing: String?, block: String): String =
            if (existing.isNullOrBlank()) block + "\n" else existing.trimEnd('\n') + "\n" + block + "\n"

        fun appendStart(existing: String?, block: String): String {
            if (existing.isNullOrBlank()) return block + "\n"
            val lines = existing.split("\n")
            val end = if (lines.first().trimEnd() == "---") (1 until lines.size).firstOrNull { lines[it].trimEnd() == "---" } else null
            return if (end == null) block + "\n" + existing
            else (lines.subList(0, end + 1) + block + lines.subList(end + 1, lines.size)).joinToString("\n")
        }
    }
}
