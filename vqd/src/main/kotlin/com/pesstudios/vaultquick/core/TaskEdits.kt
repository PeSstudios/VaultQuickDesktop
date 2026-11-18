package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.LocalTime
import java.time.ZonedDateTime

/** Hodnoty z formuláře úkolu. */
data class TaskChanges(
    val title: String,
    /** null = bez termínu. */
    val date: LocalDate?,
    val time: LocalTime?,
    val status: String,
    val priority: String,
    /** Názvy stránek projektů v pořadí z frontmatteru; prázdný = žádný. */
    val projects: List<String>,
    /** Kontexty (bez `@`) v pořadí z frontmatteru; prázdný = žádný. */
    val contexts: List<String>,
    val body: String,
)

/** Úpravy souboru úkolu z notifikace / obrazovky zpožděných. Mění jen dotčené řádky. */
object TaskEdits {
    /**
     * Odloží úkol na [date] a zachová časy. Termín se nikdy neposune dřív: scheduled (nebo u
     * úkolu jen s due samotné due) se nastaví na [date], jen když je dřív; due dřívější než
     * [date] se posune také, aby úkol nezůstal zpožděný.
     */
    fun postpone(text: String, task: Task, s: TaskNotesSettings, date: LocalDate, now: ZonedDateTime): String {
        var t = text
        fun moved(value: String?) = date.toString() + (value?.substringAfter('T', "")?.takeIf { it.isNotEmpty() }?.let { "T$it" } ?: "")
        val dueOnly = task.scheduled == null && task.due != null
        if (!dueOnly && (task.scheduledDate == null || task.scheduledDate < date)) {
            t = Frontmatter.setValue(t, s.field("scheduled"), moved(task.scheduled))
        }
        if (task.dueDate != null && task.dueDate < date) {
            t = Frontmatter.setValue(t, s.field("due"), moved(task.due))
        }
        return if (t == text) text else Frontmatter.setValue(t, s.field("dateModified"), NoteFormat.stamp(now))
    }

    /** Zrušení = archivace jako v TaskNotes: přidá archivační tag. */
    fun archive(text: String, s: TaskNotesSettings, now: ZonedDateTime): String {
        val tag = s.field("archiveTag")
        val tags = Frontmatter.parse(text).list("tags").map { it.removePrefix("#") }
        val t = if (tag in tags) text else Frontmatter.addListItem(text, "tags", tag)
        return Frontmatter.setValue(t, s.field("dateModified"), NoteFormat.stamp(now))
    }

    /** Uloží formulář: mění jen změněná pole; „bez termínu“ smaže scheduled i due. */
    fun update(text: String, task: Task, s: TaskNotesSettings, c: TaskChanges, now: ZonedDateTime): String {
        var t = text
        if (c.title.trim() != task.title) t = Frontmatter.setValue(t, s.field("title"), NoteFormat.yaml(c.title.trim()))
        if (c.date != task.date || c.time != task.time) {
            t = if (c.date == null) {
                Frontmatter.removeKey(Frontmatter.removeKey(t, s.field("scheduled")), s.field("due"))
            } else {
                val value = c.date.toString() + (c.time?.let { "T" + it.toString().take(5) } ?: "")
                if (task.scheduled == null && task.due != null) {
                    // Úkol jen s due – posunout due (scheduled navíc by termín neposunul, platí dřívější).
                    Frontmatter.setValue(t, s.field("due"), value)
                } else {
                    var x = Frontmatter.setValue(t, s.field("scheduled"), value)
                    // Dřívější due by úkol nechalo na starém termínu.
                    val due = task.dueDate
                    if (due != null && due < c.date) {
                        val dueTime = task.due?.substringAfter('T', "")?.takeIf { it.isNotEmpty() }
                        x = Frontmatter.setValue(x, s.field("due"), c.date.toString() + (dueTime?.let { "T$it" } ?: ""))
                    }
                    x
                }
            }
        }
        if (c.status != task.status) {
            t = Frontmatter.setValue(t, s.field("status"), c.status)
            val wasDone = task.status in s.completedStatuses
            val isDone = c.status in s.completedStatuses
            if (isDone && !wasDone) t = Frontmatter.setValue(t, s.field("completedDate"), now.toLocalDate().toString())
            if (!isDone && wasDone) t = Frontmatter.removeKey(t, s.field("completedDate"))
        }
        if (c.priority != task.priority) t = Frontmatter.setValue(t, s.field("priority"), c.priority)
        val projects = c.projects.map { it.trim() }.filter { it.isNotEmpty() }.distinctBy { it.lowercase() }
        if (projects != task.projects) {
            // Jen odebrané a přidané položky – ostatní zůstanou, jak byly zapsané (alias, cesta, uvozovky).
            val key = s.field("projects")
            fun Collection<String>.has(p: String) = any { it.equals(p, ignoreCase = true) }
            val removed = task.projects.filterNot { projects.has(it) }
            if (removed.isNotEmpty()) t = Frontmatter.removeListItems(t, key) { v -> TaskNotes.linkTarget(v)?.let(removed::has) == true }
            projects.filterNot { task.projects.has(it) }.forEach { t = Frontmatter.addListItem(t, key, "\"[[$it]]\"") }
            if (projects.isEmpty()) t = Frontmatter.removeKey(t, key)
        }
        val contexts = c.contexts.map { it.trim().removePrefix("@") }.filter { it.isNotEmpty() }.distinctBy(Places::normalizeContext)
        val oldNorm = task.contexts.map(Places::normalizeContext)
        val newNorm = contexts.map(Places::normalizeContext)
        if (newNorm.toSet() != oldNorm.toSet() || newNorm.size != oldNorm.distinct().size) {
            // Jen odebrané a přidané kontexty – ostatní zůstanou zapsané, jak byly (`@`, uvozovky).
            val key = s.field("contexts")
            val removed = oldNorm.filterNot { it in newNorm }.toSet()
            if (removed.isNotEmpty()) t = Frontmatter.removeListItems(t, key) { v -> Places.normalizeContext(v) in removed }
            contexts.filter { Places.normalizeContext(it) !in oldNorm }.forEach { t = Frontmatter.addListItem(t, key, NoteFormat.yaml(it)) }
            if (contexts.isEmpty()) t = Frontmatter.removeKey(t, key)
        }
        if (c.body.trim() != bodyOf(t)) {
            var head = t.substring(0, t.length - afterFrontmatter(t).length)
            // Soubor končící hned za `---` – bez nového řádku by se uzavírací čára slepila s textem.
            if (head.isNotEmpty() && !head.endsWith("\n")) head += "\n"
            val body = c.body.trim()
            t = head + (if (body.isEmpty()) "" else body + "\n")
        }
        return Frontmatter.setValue(t, s.field("dateModified"), NoteFormat.stamp(now))
    }

    /** Tělo úkolu (vše za frontmatterem), oříznuté. */
    fun bodyOf(text: String): String = afterFrontmatter(text).trim()

    private fun afterFrontmatter(text: String): String {
        val lines = text.split("\n")
        if (lines.firstOrNull()?.trim() != "---") return text
        val end = (1 until lines.size).firstOrNull { lines[it].trim() == "---" } ?: return text
        return lines.drop(end + 1).joinToString("\n")
    }
}
