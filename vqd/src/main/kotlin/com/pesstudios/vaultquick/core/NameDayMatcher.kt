package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.temporal.ChronoUnit

object NameDayMatcher {

    // Convention seen throughout the vault is "Příjmení Jméno" (surname first), so the given
    // name to look up is the last whitespace-separated word of the file name.
    fun computeUpcoming(people: List<PersonNote>, today: LocalDate, daysAhead: Int): List<Anniversary> {
        return people.mapNotNull { person ->
            val givenName = person.fileName.trim().substringAfterLast(' ')
            val (day, month) = CzechNameDays.dayMonthByName[givenName] ?: return@mapNotNull null
            val next = nextOccurrence(day, month, today)
            val daysUntil = ChronoUnit.DAYS.between(today, next)
            if (daysUntil !in 0..daysAhead.toLong()) return@mapNotNull null

            Anniversary(
                noteName = person.fileName,
                notePath = person.relativePath,
                typ = "svátek",
                misto = "",
                popisek = "",
                nextOccurrence = next,
                kolikate = 0,
                daysUntil = daysUntil,
                isNameDay = true,
            )
        }
    }

    private fun nextOccurrence(day: Int, month: Int, today: LocalDate): LocalDate {
        val thisYear = LocalDate.of(today.year, month, day)
        return if (thisYear.isBefore(today)) LocalDate.of(today.year + 1, month, day) else thisYear
    }
}
