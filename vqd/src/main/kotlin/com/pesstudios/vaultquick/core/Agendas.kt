package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.LocalTime

data class AgendaEntry(
    val task: Task,
    /** Datum výskytu; null jen v sekci bez termínu. */
    val date: LocalDate?,
    val time: LocalTime?,
    /** Lze odškrtnout: běžný úkol nebo nejbližší výskyt opakovaného. */
    val checkable: Boolean,
    /** Budoucí výskyt opakovaného úkolu (🔁). */
    val occurrence: Boolean,
    /** Hotovo z widgetu půjde provést; false = nepodporované opakování → otevřít formulář. */
    val completable: Boolean = true,
)

data class AgendaDay(val date: LocalDate, val entries: List<AgendaEntry>)

data class AgendaView(val overdue: List<AgendaEntry>, val days: List<AgendaDay>, val noDate: List<AgendaEntry>)

/** Agenda úkolů po dnech pro widget úkolů. */
object Agendas {
    /**
     * [allNoDate]: sekce bez termínu se všemi nesplněnými úkoly bez termínu (panel úkolů), jinak jen
     * rozpracované (`TaskNotes.next`, widget úkolů).
     */
    fun build(tasks: List<Task>, s: TaskNotesSettings, today: LocalDate, days: Int, includeNoDate: Boolean, allNoDate: Boolean = false): AgendaView {
        val end = today.plusDays(days.toLong() - 1)
        val overdue = TaskNotes.agenda(tasks, s, today).overdue.map { AgendaEntry(it, it.date, it.time, true, false, canComplete(it)) }
        // Opakovaný úkol s prošlým due je ve zpožděných – nejbližší výskyt nesmí jít odškrtnout podruhé.
        val overduePaths = overdue.map { it.task.path }.toSet()
        /** Opakované, jejichž zmeškaný výskyt nahradil dnešní – ze zpožděných pryč. */
        val replaced = mutableSetOf<String>()
        val byDay = mutableMapOf<LocalDate, MutableList<AgendaEntry>>()
        fun add(e: AgendaEntry) { byDay.getOrPut(e.date!!) { mutableListOf() } += e }
        fun inRange(d: LocalDate) = !d.isBefore(today) && !d.isAfter(end)

        for (t in tasks) {
            if (t.status in s.completedStatuses) continue
            val first = t.scheduledDate
            if (t.isRecurring && first != null) {
                val done = (t.completeInstances + t.skippedInstances)
                    .mapNotNull { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }.toSet()
                val time = timeOf(t.scheduled)
                // Dnešní výskyt jde odškrtnout, i když scheduled zůstal v minulosti (zmeškané výskyty) –
                // nahradí položku ve zpožděných.
                val todayOccurrence = TaskNotes.pendingToday(t, today)
                if (todayOccurrence) {
                    replaced += t.path
                    add(AgendaEntry(t, today, time, checkable = true, occurrence = false, completable = canComplete(t)))
                } else if (inRange(first) && first !in done && t.path !in overduePaths) {
                    add(AgendaEntry(t, first, time, checkable = true, occurrence = false, completable = canComplete(t)))
                }
                // Budoucí výskyty; nejbližší (first) je buď výše, nebo ve zpožděných.
                var prev = if (first.isBefore(today)) today.minusDays(1) else first
                var guard = 0
                while (guard++ <= days) {
                    val next = Recurrence.next(t.recurrence!!, prev, first, done + first) ?: break
                    if (next.isAfter(end)) break
                    if (!next.isBefore(today) && !(todayOccurrence && next == today)) add(AgendaEntry(t, next, time, checkable = false, occurrence = true))
                    prev = next
                }
            } else {
                val date = t.date ?: continue
                if (inRange(date)) add(AgendaEntry(t, date, t.time, checkable = true, occurrence = false))
            }
        }

        val order = compareBy<AgendaEntry, LocalTime?>(nullsLast()) { it.time }
            .thenByDescending { s.priorityWeights[it.task.priority] ?: 0 }
            .thenBy { it.task.title }
        val list = (0 until days).map { i ->
            val d = today.plusDays(i.toLong())
            AgendaDay(d, byDay[d].orEmpty().sortedWith(order))
        }
        val noDateTasks = when {
            !includeNoDate -> emptyList()
            allNoDate -> tasks
                .filter { it.status !in s.completedStatuses && it.date == null && !it.isRecurring && TaskNotes.GOAL_TAG !in it.tags }
                .sortedWith(compareByDescending<Task> { it.status == TaskNotes.IN_PROGRESS }
                    .thenByDescending { s.priorityWeights[it.priority] ?: 0 }.thenBy { it.title })
            else -> TaskNotes.next(tasks, s)
        }
        val noDate = noDateTasks.map { AgendaEntry(it, null, null, true, false) }
        return AgendaView(overdue.filter { it.task.path !in replaced }, list, noDate)
    }

    /** Projekty nesplněných úkolů (názvy poznámek) – pro filtr v panelu úkolů. Bez ohledu na velikost písmen, podle abecedy. */
    fun projects(tasks: List<Task>, s: TaskNotesSettings): List<String> = tasks
        .filter { it.status !in s.completedStatuses }
        .flatMap { it.projects }
        .filter { it.isNotBlank() }
        .distinctBy { it.lowercase() }
        .sortedBy { it.lowercase() }

    /** Úkoly zobrazené v agendě (každý jednou) – z nich se sestaví filtr projektů, aby v něm nebyly prázdné projekty. */
    fun tasksIn(view: AgendaView): List<Task> =
        (view.overdue + view.days.flatMap { it.entries } + view.noDate).map { it.task }.distinctBy { it.path }

    /** Úkoly projektu [project] (název poznámky, bez ohledu na velikost písmen); null = všechny. */
    fun ofProject(tasks: List<Task>, project: String?): List<Task> =
        if (project == null) tasks else tasks.filter { t -> t.projects.any { it.equals(project, ignoreCase = true) } }

    /**
     * Hledání v nesplněných úkolech podle názvu (bez diakritiky a velikosti písmen) bez ohledu na
     * rozsah a projekt. Každý úkol jednou s nejbližším termínem – u opakovaného nejbližší výskyt
     * (do roka); seřazeno podle data, bez termínu na konci.
     */
    fun search(tasks: List<Task>, s: TaskNotesSettings, today: LocalDate, query: String): List<AgendaEntry> {
        val words = normalize(query).split(' ').filter { it.isNotBlank() }
        if (words.isEmpty()) return emptyList()
        val found = tasks.filter { t ->
            val text = normalize(t.title + " " + t.noteName)
            t.status !in s.completedStatuses && words.all { it in text }
        }
        val v = build(found, s, today, SEARCH_DAYS, includeNoDate = true, allNoDate = true)
        val first = (v.overdue + v.days.flatMap { it.entries } + v.noDate).distinctBy { it.task.path }.associateBy { it.task.path }
        // Mimo agendu: termín za víc než rok, cíl bez termínu, opakovaný bez dalšího výskytu.
        return found.map { t -> first[t.path] ?: AgendaEntry(t, t.date, t.time, checkable = !t.isRecurring, occurrence = false, completable = !t.isRecurring) }
            .sortedWith(compareBy<AgendaEntry, LocalDate?>(nullsLast()) { it.date }.thenBy(nullsLast()) { it.time }.thenBy { it.task.title })
    }

    private const val SEARCH_DAYS = 366

    /** Počet zpožděných a dnešních úkolů (widget s počtem, dlaždice). */
    fun dueCount(tasks: List<Task>, s: TaskNotesSettings, today: LocalDate, includeOverdue: Boolean = true): Int {
        val v = build(tasks, s, today, days = 1, includeNoDate = false)
        return (if (includeOverdue) v.overdue.size else 0) + v.days.first().entries.count { !it.occurrence }
    }

    /**
     * Platí řádek widgetu (výskyt [expected]) ještě pro soubor? Chrání před dvojklikem a před
     * řádkem, který je starší než změna v Obsidianu – jinak by Hotovo splnilo další výskyt.
     */
    fun stillCurrent(t: Task?, s: TaskNotesSettings, expected: LocalDate?): Boolean {
        if (t == null || t.status in s.completedStatuses) return false
        if (!t.isRecurring) return expected == t.date
        // Opakovaný: výskyt ještě nesplněný ani nepřeskočený (může to být i dnešní při zmeškaném scheduled).
        return expected != null && expected.toString() !in t.completeInstances && expected.toString() !in t.skippedInstances
    }

    /** Jde Hotovo provést (běžný úkol, nebo opakování, které umíme spočítat)? */
    private fun canComplete(t: Task): Boolean {
        if (!t.isRecurring) return true
        val first = t.scheduledDate ?: return false
        return Recurrence.next(t.recurrence!!, first, first, setOf(first)) != null
    }

    private fun timeOf(value: String?): LocalTime? =
        value?.substringAfter('T', "")?.takeIf { it.length >= 5 }?.let { runCatching { LocalTime.parse(it.take(5)) }.getOrNull() }
}
