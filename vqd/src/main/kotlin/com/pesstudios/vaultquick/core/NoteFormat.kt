package com.pesstudios.vaultquick.core

import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/** Obsah nových poznámek a úkolů (formát TaskNotes). */
object NoteFormat {
    private val MINUTE = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm")
    private val TASKNOTES_STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSXXX")
    private val SAFE_YAML = Regex("^[\\p{L}\\p{N}][^:#\"'\\[\\]{},&*!|>%@`\\n]*$")
    private val YAML_KEYWORDS = setOf("true", "false", "null", "yes", "no", "on", "off", "~")

    fun stamp(now: ZonedDateTime): String = now.format(TASKNOTES_STAMP)

    fun note(text: String, tags: List<String>, now: ZonedDateTime, project: String? = null): String = buildString {
        append("---\n")
        if (tags.isNotEmpty()) {
            append("tags:\n")
            tags.forEach { append("  - ").append(yaml(it.removePrefix("#"))).append('\n') }
        }
        append("created: ").append(now.format(MINUTE)).append('\n')
        if (project != null) append("projekt: \"[[").append(project).append("]]\"\n")
        append("zdroj: vaultquick\n")
        append("---\n")
        append(text.trim()).append('\n')
    }

    fun task(task: ParsedTask, body: String, now: ZonedDateTime, s: TaskNotesSettings, extraTags: List<String>): String = buildString {
        val stamp = stamp(now)
        append("---\n")
        append("title: ").append(yaml(task.title)).append('\n')
        append("status: ").append(yaml(s.defaultStatus)).append('\n')
        append("priority: ").append(if (task.highPriority) "high" else "normal").append('\n')
        if (task.project != null) append("projects:\n  - \"[[").append(task.project).append("]]\"\n")
        if (task.contexts.isNotEmpty()) {
            append(s.field("contexts")).append(":\n")
            task.contexts.forEach { append("  - ").append(yaml(it)).append('\n') }
        }
        task.date?.let { date ->
            append("scheduled: ").append(date)
            task.time?.let { append('T').append(it.toString().take(5)) }
            append('\n')
        }
        append("dateCreated: ").append(stamp).append('\n')
        append("dateModified: ").append(stamp).append('\n')
        append("tags:\n")
        (listOf(s.taskTag) + extraTags.map { it.removePrefix("#") }).distinct()
            .forEach { append("  - ").append(yaml(it)).append('\n') }
        append("zdroj: vaultquick\n")
        append("---\n")
        if (body.isNotBlank()) append(body.trim()).append('\n')
    }

    fun yaml(value: String): String {
        val safe = SAFE_YAML.matches(value) && !value.endsWith(" ") &&
            value.lowercase() !in YAML_KEYWORDS && value.toDoubleOrNull() == null
        return if (safe) value else "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    }
}
