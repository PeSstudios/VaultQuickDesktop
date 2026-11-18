package com.pesstudios.vaultquick.core

import java.time.Duration
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.OffsetDateTime

class Reminder(val path: String, val title: String, val at: LocalDateTime) {
    /** Stabilní id pro AlarmManager i notifikaci. */
    val id: Int get() = (path + "@" + at).hashCode()
}

/**
 * Kdy upozornit na úkoly: podle `reminders` z TaskNotes, a když úkol žádné nemá,
 * v čas uvedený u termínu (scheduled/due s časem).
 */
object Reminders {
    /** Úkol jen s datem (bez času) – relativní připomínka se počítá od tohoto času. */
    val DATE_ONLY_TIME: LocalTime = LocalTime.of(9, 0)

    fun forTasks(tasks: List<Task>, s: TaskNotesSettings, now: LocalDateTime, horizonDays: Long = 7): List<Reminder> {
        val horizon = now.plusDays(horizonDays)
        return tasks.filter { TaskNotes.isPending(it, s) }.flatMap { t ->
            val times = if (t.reminders.isNotEmpty()) t.reminders.mapNotNull { resolve(it, t) }
            else listOfNotNull(t.time?.let { time -> t.date?.atTime(time) })
            times.filter { it.isAfter(now) && !it.isAfter(horizon) }.distinct().map { Reminder(t.path, t.title, it) }
        }.sortedBy { it.at }
    }

    fun resolve(r: Map<String, String>, t: Task): LocalDateTime? = when (r["type"]) {
        "absolute" -> r["absoluteTime"]?.let { parseDateTime(it) }
        "relative" -> {
            val (date, time) = if (r["relatedTo"] == "due") t.dueDate to timeOf(t.due) else t.scheduledDate to timeOf(t.scheduled)
            val offset = r["offset"]?.let(::parseOffset)
            if (date == null || offset == null) null else date.atTime(time ?: DATE_ONLY_TIME).plus(offset)
        }
        else -> null
    }

    /** ISO 8601 trvání s volitelným znaménkem: `-P1D`, `-PT15M`, `PT0S`, `-P1W`. */
    fun parseOffset(value: String): Duration? {
        val v = value.trim()
        val negative = v.startsWith("-")
        val body = v.removePrefix("-").removePrefix("+")
        val weeks = Regex("^P(\\d+)W$").matchEntire(body)
        val d = if (weeks != null) Duration.ofDays(weeks.groupValues[1].toLong() * 7)
        else runCatching { Duration.parse(body) }.getOrNull() ?: return null
        return if (negative) d.negated() else d
    }

    private fun parseDateTime(value: String): LocalDateTime? =
        runCatching { OffsetDateTime.parse(value).atZoneSameInstant(java.time.ZoneId.systemDefault()).toLocalDateTime() }.getOrNull()
            ?: runCatching { LocalDateTime.parse(value) }.getOrNull()

    private fun timeOf(value: String?): LocalTime? =
        value?.substringAfter('T', "")?.takeIf { it.length >= 5 }?.let { runCatching { LocalTime.parse(it.take(5)) }.getOrNull() }
}
