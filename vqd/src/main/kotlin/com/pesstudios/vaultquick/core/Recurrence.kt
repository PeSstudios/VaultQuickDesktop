package com.pesstudios.vaultquick.core

import java.time.DayOfWeek
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import java.time.temporal.TemporalAdjusters

/**
 * Podmnožina RRULE, kterou zapisuje TaskNotes: FREQ=DAILY/WEEKLY/MONTHLY/YEARLY,
 * INTERVAL, BYDAY (týdně), BYMONTHDAY (měsíčně), DTSTART, UNTIL.
 */
object Recurrence {
    private val SUPPORTED = setOf("DTSTART", "FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "UNTIL", "WKST")
    private val DAYS = mapOf(
        "MO" to DayOfWeek.MONDAY, "TU" to DayOfWeek.TUESDAY, "WE" to DayOfWeek.WEDNESDAY,
        "TH" to DayOfWeek.THURSDAY, "FR" to DayOfWeek.FRIDAY, "SA" to DayOfWeek.SATURDAY, "SU" to DayOfWeek.SUNDAY,
    )

    /**
     * První výskyt po [after], který není v [done].
     * null = pravidlo neumíme (otevřít v Obsidianu) nebo série skončila.
     */
    fun next(rule: String, after: LocalDate, anchor: LocalDate, done: Set<LocalDate>): LocalDate? {
        val parts = rule.split(';').mapNotNull { token ->
            val sep = token.indexOfFirst { it == '=' || it == ':' }
            if (sep <= 0) null else token.substring(0, sep).trim().uppercase() to token.substring(sep + 1).trim()
        }.toMap()
        if (parts.keys.any { it !in SUPPORTED }) return null
        val start = parts["DTSTART"]?.let(::basicDate) ?: anchor
        val until = parts["UNTIL"]?.let(::basicDate)
        val interval = parts["INTERVAL"]?.toIntOrNull()?.takeIf { it > 0 } ?: 1

        val matches: (LocalDate) -> Boolean = when (parts["FREQ"]) {
            "DAILY" -> { d -> ChronoUnit.DAYS.between(start, d) % interval == 0L }
            "WEEKLY" -> {
                val days = parts["BYDAY"]?.split(',')?.map { DAYS[it.trim()] ?: return null }?.toSet() ?: setOf(start.dayOfWeek)
                val startWeek = start.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY))
                val f: (LocalDate) -> Boolean = { d ->
                    d.dayOfWeek in days &&
                        ChronoUnit.WEEKS.between(startWeek, d.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY))) % interval == 0L
                }
                f
            }
            "MONTHLY" -> {
                if (parts.containsKey("BYDAY")) return null
                val monthDays = parts["BYMONTHDAY"]?.split(',')?.map { it.trim().toIntOrNull() ?: return null } ?: listOf(start.dayOfMonth)
                val f: (LocalDate) -> Boolean = { d ->
                    val months = ChronoUnit.MONTHS.between(start.withDayOfMonth(1), d.withDayOfMonth(1))
                    months % interval == 0L && monthDays.any { md ->
                        if (md > 0) d.dayOfMonth == md else d.dayOfMonth == d.lengthOfMonth() + 1 + md
                    }
                }
                f
            }
            "YEARLY" -> {
                if (parts.containsKey("BYDAY") || parts.containsKey("BYMONTHDAY")) return null
                val f: (LocalDate) -> Boolean = { d ->
                    (d.year - start.year) % interval == 0 && d.month == start.month && d.dayOfMonth == start.dayOfMonth
                }
                f
            }
            else -> return null
        }

        var d = after.plusDays(1)
        val limit = after.plusYears(5)
        while (d <= limit) {
            if (until != null && d > until) return null
            if (d >= start && d !in done && matches(d)) return d
            d = d.plusDays(1)
        }
        return null
    }

    /** "20260922" nebo "20260922T090000Z" → datum. */
    private fun basicDate(value: String): LocalDate? = try {
        LocalDate.of(value.substring(0, 4).toInt(), value.substring(4, 6).toInt(), value.substring(6, 8).toInt())
    } catch (_: Exception) {
        null
    }
}
