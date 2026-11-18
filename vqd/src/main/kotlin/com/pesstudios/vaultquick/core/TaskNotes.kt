package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.LocalTime
import java.time.ZonedDateTime

/** Nastavení pluginu TaskNotes, která launcher potřebuje (z .obsidian/plugins/tasknotes/data.json). */
class TaskNotesSettings(
    val tasksFolder: String = "TaskNotes",
    val taskTag: String = "task",
    val defaultStatus: String = "open",
    val doneStatus: String = "done",
    val completedStatuses: Set<String> = setOf("done"),
    val priorityWeights: Map<String, Int> = mapOf("high" to 3, "normal" to 2, "low" to 1, "none" to 0),
    /** Všechny stavy z customStatuses (pro výběr ve formuláři úkolu). */
    val statuses: List<String> = listOf("open", "in-progress", "done"),
    private val fields: Map<String, String> = emptyMap(),
) {
    fun field(name: String): String = fields[name] ?: DEFAULT_FIELDS[name] ?: name

    /** Otisk nastavení, která ovlivňují načtené úkoly – při změně se zahodí cache. */
    val signature: String
        get() = listOf(taskTag, field("archiveTag"), field("title"), field("status"), field("priority"),
            field("scheduled"), field("due"), field("recurrence"), field("completeInstances"), field("skippedInstances"),
            field("projects"), field("reminders"), field("contexts"), field("completedDate"), "v5",
        ).joinToString("|")

    companion object {
        private val DEFAULT_FIELDS = mapOf(
            "completeInstances" to "complete_instances",
            "skippedInstances" to "skipped_instances",
            "archiveTag" to "archived",
        )

        fun parse(text: String): TaskNotesSettings {
            return try {
                val json = org.json.JSONObject(text)
                val statuses = json.optJSONArray("customStatuses")
                val completed = mutableSetOf<String>()
                val all = mutableListOf<String>()
                if (statuses != null) for (i in 0 until statuses.length()) {
                    val s = statuses.getJSONObject(i)
                    all += s.getString("value")
                    if (s.optBoolean("isCompleted")) completed += s.getString("value")
                }
                val priorities = json.optJSONArray("customPriorities")
                val weights = mutableMapOf<String, Int>()
                if (priorities != null) for (i in 0 until priorities.length()) {
                    val p = priorities.getJSONObject(i)
                    weights[p.getString("value")] = p.optInt("weight")
                }
                val mapping = json.optJSONObject("fieldMapping")
                val fields = mutableMapOf<String, String>()
                mapping?.keys()?.forEach { key -> mapping.optString(key).takeIf { it.isNotEmpty() }?.let { fields[key] = it } }
                TaskNotesSettings(
                    tasksFolder = json.optString("tasksFolder", "TaskNotes"),
                    taskTag = json.optString("taskTag", "task"),
                    defaultStatus = json.optString("defaultTaskStatus", "open"),
                    doneStatus = completed.firstOrNull { it == "done" } ?: completed.firstOrNull() ?: "done",
                    completedStatuses = completed.ifEmpty { setOf("done") },
                    statuses = all.ifEmpty { listOf("open", "in-progress", "done") },
                    priorityWeights = weights.ifEmpty { mapOf("high" to 3, "normal" to 2, "low" to 1, "none" to 0) },
                    fields = fields,
                )
            } catch (_: Exception) {
                TaskNotesSettings()
            }
        }
    }
}

class Task(
    val path: String,
    val title: String,
    val status: String,
    val priority: String,
    val scheduled: String?,
    val due: String?,
    val recurrence: String?,
    val completeInstances: List<String>,
    val skippedInstances: List<String>,
    val tags: List<String> = emptyList(),
    /** Odkazy na nadřazené úkoly/cíle (`projects: ["[[Cíl]]"]`) jako názvy poznámek. */
    val projects: List<String> = emptyList(),
    val area: String? = null,
    /** Připomínky TaskNotes (`type`, `relatedTo`, `offset`, `absoluteTime`…). */
    val reminders: List<Map<String, String>> = emptyList(),
    val contexts: List<String> = emptyList(),
    /** Datum splnění (TaskNotes `completedDate`), jen u běžných úkolů. */
    val completedDate: LocalDate? = null,
) {
    /** Název poznámky bez cesty a přípony – na něj míří odkazy [[…]]. */
    val noteName: String get() = path.substringAfterLast('/').removeSuffix(".md")

    val scheduledDate: LocalDate? = dateOf(scheduled)
    val dueDate: LocalDate? = dateOf(due)

    /** Nejbližší z termínů scheduled / due. */
    val date: LocalDate? = listOfNotNull(scheduledDate, dueDate).minOrNull()
    val time: LocalTime? = when {
        date == null -> null
        date == scheduledDate -> timeOf(scheduled)
        else -> timeOf(due)
    }
    val isRecurring: Boolean = !recurrence.isNullOrBlank()

    private companion object {
        fun dateOf(value: String?): LocalDate? =
            value?.take(10)?.let { runCatching { LocalDate.parse(it) }.getOrNull() }

        fun timeOf(value: String?): LocalTime? =
            value?.substringAfter('T', "")?.takeIf { it.length >= 5 }?.let { runCatching { LocalTime.parse(it.take(5)) }.getOrNull() }
    }
}

object TaskNotes {
    /** Status, který považujeme za "právě na tom dělám" (výběr dalšího kroku bez termínu). */
    const val IN_PROGRESS = "in-progress"
    const val GOAL_TAG = "cíl"
    const val AREA_FIELD = "oblast"

    fun parseTask(path: String, text: String, s: TaskNotesSettings): Task? {
        val fm = Frontmatter.parse(text)
        val tags = fm.list("tags").map { it.removePrefix("#") }
        if (s.taskTag !in tags || s.field("archiveTag") in tags) return null
        return Task(
            path = path,
            title = fm.str(s.field("title")) ?: path.substringAfterLast('/').removeSuffix(".md"),
            status = fm.str(s.field("status")) ?: s.defaultStatus,
            priority = fm.str(s.field("priority")) ?: "normal",
            scheduled = fm.str(s.field("scheduled")),
            due = fm.str(s.field("due")),
            recurrence = fm.str(s.field("recurrence")),
            completeInstances = fm.list(s.field("completeInstances")),
            skippedInstances = fm.list(s.field("skippedInstances")),
            tags = tags,
            projects = fm.list(s.field("projects")).mapNotNull(::linkTarget),
            area = fm.str(AREA_FIELD),
            reminders = Frontmatter.objects(text, s.field("reminders")),
            contexts = fm.list(s.field("contexts")).map { it.removePrefix("@") },
            completedDate = fm.str(s.field("completedDate"))?.take(10)?.let { runCatching { LocalDate.parse(it) }.getOrNull() },
        )
    }

    /** `[[cesta/Název|alias]]` → `Název`; prostý text nechá být. */
    fun linkTarget(value: String): String? {
        val inner = value.trim().removePrefix("[[").removeSuffix("]]").substringBefore('|').substringBefore('#').trim()
        return inner.substringAfterLast('/').removeSuffix(".md").takeIf { it.isNotEmpty() }
    }

    fun isCompleted(t: Task, s: TaskNotesSettings) = t.status in s.completedStatuses

    private fun isActive(t: Task, s: TaskNotesSettings) = t.status !in s.completedStatuses

    /** Aktivní a (u opakovaných) s nesplněným aktuálním výskytem. */
    fun isPending(t: Task, s: TaskNotesSettings) =
        isActive(t, s) && !(t.isRecurring && t.scheduledDate?.toString() in t.completeInstances)

    class Agenda(val today: List<Task>, val overdue: List<Task>)

    /**
     * Dnešní úkoly (podle času a priority) a zpožděné (nejčerstvější první – staré zapomenuté
     * úkoly nemají přebít to, co je aktuální). Opakované jen se nesplněným výskytem.
     */
    fun agenda(tasks: List<Task>, s: TaskNotesSettings, today: LocalDate): Agenda {
        val due = tasks.filter { t -> isPending(t, s) && t.date != null && t.date <= today }
        val byTimeAndPriority = compareBy<Task> { it.time ?: LocalTime.MAX }
            .thenByDescending { s.priorityWeights[it.priority] ?: 0 }
            .thenBy { it.title }
        return Agenda(
            today = due.filter { it.date == today }.sortedWith(byTimeAndPriority),
            overdue = due.filter { it.date!! < today }
                .sortedWith(compareByDescending<Task> { it.date }.then(byTimeAndPriority)),
        )
    }

    /**
     * Připadá na [today] nesplněný výskyt opakovaného úkolu? Platí i když scheduled zůstal
     * v minulosti (zmeškané výskyty) – dnešní výskyt je pak ten, který se má potvrdit.
     */
    fun pendingToday(t: Task, today: LocalDate): Boolean {
        val first = t.scheduledDate ?: return false
        if (!t.isRecurring || first.isAfter(today)) return false
        val done = (t.completeInstances + t.skippedInstances).mapNotNull { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }.toSet()
        if (today in done) return false
        return first == today || Recurrence.next(t.recurrence!!, today.minusDays(1), first, done + first) == today
    }

    /** Další krok, když na dnešek nic není: rozdělané úkoly bez termínu, důležité první. */
    fun next(tasks: List<Task>, s: TaskNotesSettings): List<Task> = tasks
        .filter { it.status == IN_PROGRESS && it.date == null && !it.isRecurring && GOAL_TAG !in it.tags }
        .sortedWith(compareByDescending<Task> { s.priorityWeights[it.priority] ?: 0 }.thenBy { it.title })

    /**
     * Odškrtnutí jako v TaskNotes: běžný úkol → status done + completedDate;
     * opakovaný → výskyt [instance] (výchozí scheduled) do complete_instances a scheduled na další
     * výskyt po něm (zmeškané starší výskyty se tím přeskočí – jako v TaskNotes).
     * null = opakování neumíme spočítat.
     */
    fun complete(text: String, task: Task, s: TaskNotesSettings, now: ZonedDateTime, instance: LocalDate? = null): String? {
        val stamp = NoteFormat.stamp(now)
        if (!task.isRecurring) {
            var t = Frontmatter.setValue(text, s.field("status"), s.doneStatus)
            t = Frontmatter.setValue(t, s.field("completedDate"), now.toLocalDate().toString())
            return Frontmatter.setValue(t, s.field("dateModified"), stamp)
        }
        val anchor = task.scheduledDate ?: return null
        // Bez určeného výskytu (notifikace, přehled zpožděných): dnešní, připadá-li na dnešek, jinak scheduled.
        val day = instance ?: now.toLocalDate().takeIf { pendingToday(task, it) } ?: anchor
        val done = (task.completeInstances + task.skippedInstances)
            .mapNotNull { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }.toSet() + day
        val next = Recurrence.next(task.recurrence!!, day, anchor, done) ?: return null
        val time = task.scheduled?.substringAfter('T', "")?.takeIf { it.isNotEmpty() }
        var t = Frontmatter.addListItem(text, s.field("completeInstances"), day.toString())
        t = Frontmatter.setValue(t, s.field("scheduled"), next.toString() + (time?.let { "T$it" } ?: ""))
        return Frontmatter.setValue(t, s.field("dateModified"), stamp)
    }
}
