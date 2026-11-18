package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.temporal.ChronoUnit

enum class ContactScope { ALL, LABELS }

/** Co zobrazovat – jeden společný filtr pro widgety i Připomínkovač. */
data class AnniversaryFilter(
    val daysAhead: Int = 31,
    /** Typy výročí z vaultu; prázdná množina = všechny. */
    val types: Set<String> = emptySet(),
    val vaultAnniversaries: Boolean = true,
    val vaultNameDays: Boolean = true,
    val contactNameDays: Boolean = false,
    val contactBirthdays: Boolean = false,
    val contactScope: ContactScope = ContactScope.ALL,
    val contactLabels: Set<String> = emptySet(),
)

enum class UpcomingKind { ANNIVERSARY, NAME_DAY, CONTACT_BIRTHDAY, CONTACT_NAME_DAY }

sealed interface ItemSource {
    /** Relativní cesta poznámky včetně `.md`. */
    data class Note(val path: String) : ItemSource
    data class Contact(val id: Long, val lookupKey: String) : ItemSource
}

data class UpcomingItem(
    val kind: UpcomingKind,
    val name: String,
    val type: String,
    val date: LocalDate,
    val daysUntil: Int,
    /** Kolikáté; null u svátků, narozenin bez roku a událostí z letošního roku (0.). */
    val ordinal: Int?,
    val place: String,
    val label: String,
    val source: ItemSource,
)

object UpcomingAnniversaries {
    const val NAME_DAY_TYPE = "svátek"
    const val BIRTHDAY_TYPE = "narozeniny"

    fun compute(
        anniversaries: List<RawAnniversary>,
        people: List<PersonNote>,
        contacts: List<ContactPerson>,
        settings: AnniversarySettings,
        filter: AnniversaryFilter,
        today: LocalDate,
        calendar: NameDayCalendar = NameDayCalendar.CZECH,
    ): List<UpcomingItem> {
        val items = mutableListOf<UpcomingItem>()

        if (filter.vaultAnniversaries) for (raw in anniversaries) {
            if (filter.types.isNotEmpty() && raw.typ !in filter.types) continue
            val a = AnniversaryCalculator.compute(raw, today) ?: continue
            items += UpcomingItem(UpcomingKind.ANNIVERSARY, raw.noteName, raw.typ, a.nextOccurrence, a.daysUntil.toInt(),
                a.kolikate.takeIf { it > 0 }, raw.misto, raw.popisek, ItemSource.Note(raw.notePath))
        }

        val vaultNameDayKeys = mutableSetOf<String>()
        if (filter.vaultNameDays) for (p in people) {
            val name = PersonNames.parse(p.fileName, settings.nameOrder)
            name.key?.let(vaultNameDayKeys::add)
            val date = calendar.next(name.given, today) ?: continue
            items += UpcomingItem(UpcomingKind.NAME_DAY, p.fileName, NAME_DAY_TYPE, date, days(today, date), null, "", "", ItemSource.Note(p.relativePath))
        }

        // Narozeniny z vaultu ruší narozeniny z kontaktu i tehdy, když se výročí z vaultu nezobrazují.
        val vaultBirthdayKeys = anniversaries.filter { it.typ.equals(BIRTHDAY_TYPE, ignoreCase = true) }
            .mapNotNull { PersonNames.parse(it.noteName, settings.nameOrder).key }.toSet()
        val contactNameDayKeys = mutableSetOf<String>()
        val contactBirthdayKeys = mutableSetOf<String>()
        for (c in contacts.distinctBy { it.id }) {
            val name = c.name()
            val key = name.key
            val source = ItemSource.Contact(c.id, c.lookupKey)
            if (filter.contactNameDays && (key == null || (key !in vaultNameDayKeys && contactNameDayKeys.add(key)))) {
                calendar.next(name.given, today)?.let { date ->
                    items += UpcomingItem(UpcomingKind.CONTACT_NAME_DAY, c.displayName, NAME_DAY_TYPE, date, days(today, date), null, "", "", source)
                }
            }
            val b = c.birthday
            if (filter.contactBirthdays && b != null && (key == null || (key !in vaultBirthdayKeys && contactBirthdayKeys.add(key)))) {
                val date = next(b.month, b.day, today)
                items += UpcomingItem(UpcomingKind.CONTACT_BIRTHDAY, c.displayName, BIRTHDAY_TYPE, date, days(today, date),
                    b.year?.let { date.year - it }?.takeIf { it > 0 }, "", "", source)
            }
        }

        return items.filter { it.daysUntil in 0..filter.daysAhead }
            .sortedWith(compareBy<UpcomingItem>({ it.daysUntil }, { it.name }))
    }

    /** Nejbližší výskyt dne v roce (dnes nebo později); 29. 2. v nepřestupném roce → 28. 2. */
    private fun next(month: Int, day: Int, today: LocalDate): LocalDate {
        fun inYear(year: Int): LocalDate {
            val first = LocalDate.of(year, month, 1)
            return first.withDayOfMonth(minOf(day, first.lengthOfMonth()))
        }
        val thisYear = inYear(today.year)
        return if (thisYear.isBefore(today)) inYear(today.year + 1) else thisYear
    }

    private fun days(from: LocalDate, to: LocalDate) = ChronoUnit.DAYS.between(from, to).toInt()
}
