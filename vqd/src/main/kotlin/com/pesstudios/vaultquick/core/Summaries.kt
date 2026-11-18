package com.pesstudios.vaultquick.core

import java.time.DayOfWeek
import java.time.LocalDate

data class MorningSummary(
    val today: List<Task>,
    val todayCount: Int,
    val overdueCount: Int,
    val anniversaries: List<UpcomingItem>,
)

object MorningSummaries {
    private const val MAX_TASKS = 5

    /** null = není co poslat. [upcoming] = výročí ze snímku (společný filtr). */
    fun build(tasks: List<Task>, s: TaskNotesSettings, upcoming: List<UpcomingItem>, today: LocalDate): MorningSummary? {
        val agenda = TaskNotes.agenda(tasks, s, today)
        val anniversaries = upcoming.filter { it.daysUntil == 0 }
        if (agenda.today.isEmpty() && agenda.overdue.isEmpty() && anniversaries.isEmpty()) return null
        return MorningSummary(agenda.today.take(MAX_TASKS), agenda.today.size, agenda.overdue.size, anniversaries)
    }
}

object AnniversaryHeadsUp {
    fun items(upcoming: List<UpcomingItem>, leadDays: Int): List<UpcomingItem> =
        if (leadDays <= 0) emptyList() else upcoming.filter { it.daysUntil == leadDays }
}

data class EveningBalance(
    val done: Int,
    val total: Int,
    val remaining: List<Task>,
    val stale: List<Task>,
)

object EveningBalances {
    fun build(tasks: List<Task>, s: TaskNotesSettings, today: LocalDate, weeklyStale: Boolean): EveningBalance? {
        // Splněný dnes, nebo úkol s dnešním termínem splněný už dříve.
        fun doneToday(t: Task) = t.completedDate == today || today.toString() in t.completeInstances ||
            (t.date == today && TaskNotes.isCompleted(t, s))
        val todays = tasks.filter { s.field("archiveTag") !in it.tags && (it.date == today || doneToday(it)) }
        val done = todays.count(::doneToday)
        val remaining = todays.filter { !doneToday(it) && TaskNotes.isPending(it, s) }
        val stale = if (weeklyStale && today.dayOfWeek == DayOfWeek.SUNDAY) StaleTasks.find(tasks, s, today) else emptyList()
        if (todays.isEmpty() && stale.isEmpty()) return null
        return EveningBalance(done, todays.size, remaining, stale)
    }
}

object StaleTasks {
    /** Nesplněné úkoly s termínem starším než [olderThanDays] dní, nejstarší první. */
    fun find(tasks: List<Task>, s: TaskNotesSettings, today: LocalDate, olderThanDays: Int = 7): List<Task> {
        val limit = today.minusDays(olderThanDays.toLong())
        return tasks.filter { TaskNotes.isPending(it, s) && it.date != null && it.date < limit }.sortedBy { it.date }
    }
}
