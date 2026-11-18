package com.pesstudios.vaultquick.core

import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalTime
import java.time.temporal.TemporalAdjusters

data class ParsedTask(
    val title: String,
    val date: LocalDate?,
    val time: LocalTime?,
    val highPriority: Boolean,
    /** Cíl, ke kterému úkol patří (název poznámky), nebo null. */
    val project: String? = null,
    /** Kontexty zapsané jako @slovo (bez @, v pořadí výskytu, bez duplicit). */
    val contexts: List<String> = emptyList(),
)

/**
 * Jednoduché rozpoznání termínu z řádku úkolu (česky i anglicky):
 * "dnes", "zítra", "pozítří", "v pátek", "today", "tomorrow", "on friday", "7.10.", "7. 10. 2026",
 * "10:00", "!" = vysoká priorita.
 * Rozpoznaná slova se z názvu odstraní.
 */
object TaskParser {
    private val WEEKDAYS = mapOf(
        "pondeli" to DayOfWeek.MONDAY,
        "utery" to DayOfWeek.TUESDAY,
        "streda" to DayOfWeek.WEDNESDAY, "stredu" to DayOfWeek.WEDNESDAY,
        "ctvrtek" to DayOfWeek.THURSDAY,
        "patek" to DayOfWeek.FRIDAY,
        "sobota" to DayOfWeek.SATURDAY, "sobotu" to DayOfWeek.SATURDAY,
        "nedele" to DayOfWeek.SUNDAY, "nedeli" to DayOfWeek.SUNDAY,
        "monday" to DayOfWeek.MONDAY, "tuesday" to DayOfWeek.TUESDAY, "wednesday" to DayOfWeek.WEDNESDAY,
        "thursday" to DayOfWeek.THURSDAY, "friday" to DayOfWeek.FRIDAY, "saturday" to DayOfWeek.SATURDAY,
        "sunday" to DayOfWeek.SUNDAY,
    )
    private val PREPOSITIONS = setOf("v", "ve", "o", "na", "do", "on", "at", "by")
    /** Předložky, po kterých je den v týdnu termínem („v pátek“, „on friday“). */
    private val WEEKDAY_PREPOSITIONS = setOf("v", "ve", "on")
    private val TIME = Regex("^(\\d{1,2})[:.](\\d{2})$")
    private val FULL_DATE = Regex("^(\\d{1,2})\\.(\\d{1,2})\\.(\\d{4})?$")
    private val DAY_PART = Regex("^(\\d{1,2})\\.$")
    private val YEAR = Regex("^\\d{4}$")
    private val CONTEXT = Regex("^@[\\p{L}\\p{N}_-]+$")

    fun parse(line: String, today: LocalDate, now: LocalTime): ParsedTask {
        val words = line.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
        val kept = mutableListOf<String>()
        var date: LocalDate? = null
        var time: LocalTime? = null
        var high = false
        val contexts = mutableListOf<String>()

        fun dropPreposition() {
            if (kept.isNotEmpty() && normalize(kept.last()) in PREPOSITIONS) kept.removeAt(kept.lastIndex)
        }

        var i = 0
        while (i < words.size) {
            var word = words[i]
            if (word.endsWith("!")) {
                high = true
                word = word.trimEnd('!')
                if (word.isEmpty()) { i++; continue }
            }
            val key = normalize(word).trimEnd(',', ';')
            val next = words.getOrNull(i + 1)?.trimEnd(',', ';')

            val contextWord = word.trimEnd(',', ';')

            when {
                CONTEXT.matches(contextWord) -> {
                    // Duplicity (bez ohledu na velikost a diakritiku) se zahodí, platí první zápis.
                    val name = contextWord.drop(1)
                    if (contexts.none { normalize(it) == normalize(name) }) contexts += name
                }
                key == "dnes" || key == "today" -> date = today
                key == "zitra" || key == "tomorrow" -> date = today.plusDays(1)
                key == "pozitri" -> date = today.plusDays(2)
                key in WEEKDAYS && kept.isNotEmpty() && normalize(kept.last()) in WEEKDAY_PREPOSITIONS -> {
                    dropPreposition()
                    date = today.with(TemporalAdjusters.next(WEEKDAYS.getValue(key)))
                }
                TIME.matches(key) -> {
                    val (h, m) = TIME.find(key)!!.destructured
                    if (h.toInt() < 24 && m.toInt() < 60) {
                        dropPreposition()
                        time = LocalTime.of(h.toInt(), m.toInt())
                    } else kept += word
                }
                FULL_DATE.matches(key) -> {
                    val (d, mo, y) = FULL_DATE.find(key)!!.destructured
                    val parsed = dateOf(d.toInt(), mo.toInt(), y.toIntOrNull(), today)
                    if (parsed != null) { dropPreposition(); date = parsed } else kept += word
                }
                DAY_PART.matches(key) && next != null && DAY_PART.matches(next) -> {
                    val d = key.dropLast(1).toInt()
                    val mo = next.dropLast(1).toInt()
                    val yearWord = words.getOrNull(i + 2)?.takeIf { YEAR.matches(it) }
                    val parsed = dateOf(d, mo, yearWord?.toInt(), today)
                    if (parsed != null) {
                        dropPreposition()
                        date = parsed
                        i += if (yearWord != null) 2 else 1
                    } else kept += word
                }
                else -> kept += word
            }
            i++
        }

        if (time != null && date == null) {
            date = if (time.isAfter(now)) today else today.plusDays(1)
        }
        val title = kept.joinToString(" ").trim().ifEmpty { line.trim() }
        return ParsedTask(title, date, time, high, contexts = contexts)
    }

    private fun dateOf(day: Int, month: Int, year: Int?, today: LocalDate): LocalDate? {
        if (month !in 1..12 || day !in 1..31) return null
        return try {
            val candidate = LocalDate.of(year ?: today.year, month, day)
            if (year == null && candidate.isBefore(today)) candidate.plusYears(1) else candidate
        } catch (_: java.time.DateTimeException) {
            null
        }
    }
}
