package com.pesstudios.vaultquick.core

import java.time.LocalDate

/**
 * Kalendář svátků: jméno → dny v roce (den, měsíc). Vestavěný český ([CZECH]) nebo vlastní ze
 * souboru ve vaultu ([parse]). Jméno se hledá bez ohledu na velikost písmen a diakritiku.
 */
class NameDayCalendar private constructor(private val byName: Map<String, List<Pair<Int, Int>>>) {
    /** Počet jmen v kalendáři. */
    val size: Int get() = byName.size
    val isEmpty: Boolean get() = byName.isEmpty()

    /** Nejbližší svátek jména (dnes nebo později); 29. 2. v nepřestupném roce → 28. 2. */
    fun next(given: String, today: LocalDate): LocalDate? {
        if (given.isBlank()) return null
        val days = byName[normalize(given.trim())] ?: return null
        return days.minOf { (day, month) -> next(month, day, today) }
    }

    companion object {
        val EMPTY = NameDayCalendar(emptyMap())

        val CZECH: NameDayCalendar by lazy {
            of(CzechNameDays.byDayMonth.flatMap { (dayMonth, names) -> names.map { it to dayMonth } })
        }

        // `29.06 Petr, Pavel`, `1.7. Jaroslava`, `2. 7. Patricie`, nebo řádek tabulky `| 29.06 | Petr, Pavel |`.
        private val LINE = Regex("""^\|?\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*(?:\|\s*)?(.+?)\s*\|?\s*$""")

        /** Řádky s datem a jmény; ostatní (nadpisy, frontmatter, text, záhlaví tabulky) přeskočí. */
        fun parse(text: String): NameDayCalendar = of(text.lineSequence().flatMap { line ->
            val m = LINE.matchEntire(line.trim()) ?: return@flatMap emptySequence()
            val day = m.groupValues[1].toInt()
            val month = m.groupValues[2].toInt()
            if (month !in 1..12 || day !in 1..LocalDate.of(2024, month, 1).lengthOfMonth()) return@flatMap emptySequence()
            m.groupValues[3].split(',').asSequence().map { it to (day to month) }
        }.toList())

        private fun of(entries: List<Pair<String, Pair<Int, Int>>>): NameDayCalendar {
            val map = mutableMapOf<String, MutableList<Pair<Int, Int>>>()
            for ((name, dayMonth) in entries) {
                val key = normalize(name.trim())
                if (key.isNotEmpty()) map.getOrPut(key) { mutableListOf() }.add(dayMonth)
            }
            return NameDayCalendar(map)
        }

        private fun next(month: Int, day: Int, today: LocalDate): LocalDate {
            fun inYear(year: Int): LocalDate {
                val first = LocalDate.of(year, month, 1)
                return first.withDayOfMonth(minOf(day, first.lengthOfMonth()))
            }
            val thisYear = inYear(today.year)
            return if (thisYear.isBefore(today)) inYear(today.year + 1) else thisYear
        }
    }
}
