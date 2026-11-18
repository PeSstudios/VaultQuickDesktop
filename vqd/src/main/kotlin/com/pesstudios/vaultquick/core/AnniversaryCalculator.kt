package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.format.DateTimeParseException
import java.time.temporal.ChronoUnit

object AnniversaryCalculator {

    fun compute(raw: RawAnniversary, today: LocalDate): Anniversary? {
        val original = parseDate(raw.datum) ?: return null

        var next = nextOccurrenceInYear(original, today.year)
        if (next.isBefore(today)) {
            next = nextOccurrenceInYear(original, today.year + 1)
        }

        return Anniversary(
            noteName = raw.noteName,
            notePath = raw.notePath,
            typ = raw.typ,
            misto = raw.misto,
            popisek = raw.popisek,
            nextOccurrence = next,
            kolikate = next.year - original.year,
            daysUntil = ChronoUnit.DAYS.between(today, next),
        )
    }

    private fun nextOccurrenceInYear(original: LocalDate, year: Int): LocalDate {
        val maxDayInMonth = LocalDate.of(year, original.monthValue, 1).lengthOfMonth()
        val day = minOf(original.dayOfMonth, maxDayInMonth)
        return LocalDate.of(year, original.monthValue, day)
    }

    private fun parseDate(value: String): LocalDate? {
        return try {
            LocalDate.parse(value.trim())
        } catch (e: DateTimeParseException) {
            null
        }
    }
}
