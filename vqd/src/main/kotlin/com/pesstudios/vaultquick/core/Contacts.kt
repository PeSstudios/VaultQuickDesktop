package com.pesstudios.vaultquick.core

import java.time.Month

data class ContactBirthday(val month: Int, val day: Int, val year: Int?)

/** Kontakt z telefonu – jen to, co potřebují svátky a narozeniny. */
data class ContactPerson(
    val id: Long,
    val lookupKey: String,
    val displayName: String,
    val given: String,
    val family: String,
    val birthday: ContactBirthday?,
) {
    /** Strukturované jméno, jinak rozbor zobrazovaného jména ve tvaru "Jméno Příjmení". */
    fun name(): PersonName =
        if (given.isBlank() && family.isBlank()) PersonNames.parse(displayName, NameOrder.GIVEN_FIRST)
        else PersonName(given.trim(), family.trim())
}

object ContactDates {
    private val ISO = Regex("""^(\d{4})-(\d{1,2})-(\d{1,2})""")
    private val NO_YEAR = Regex("""^--(\d{2})-?(\d{2})$""")
    private val CZECH = Regex("""^(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})?$""")

    /** Formáty z ContactsContract.Event.START_DATE; neplatné datum → null. */
    fun parse(value: String): ContactBirthday? {
        val v = value.trim()
        ISO.find(v)?.let { return make(it.groupValues[2], it.groupValues[3], it.groupValues[1]) }
        NO_YEAR.matchEntire(v)?.let { return make(it.groupValues[1], it.groupValues[2], null) }
        CZECH.matchEntire(v)?.let { return make(it.groupValues[2], it.groupValues[1], it.groupValues[3].ifEmpty { null }) }
        return null
    }

    private fun make(month: String, day: String, year: String?): ContactBirthday? {
        val m = month.toInt()
        val d = day.toInt()
        if (m !in 1..12 || d !in 1..Month.of(m).maxLength()) return null
        // Neznámý rok ukládají některé aplikace jako 1604 nebo 0000.
        val y = year?.toInt()?.takeIf { it >= 1700 }
        return ContactBirthday(m, d, y)
    }
}
