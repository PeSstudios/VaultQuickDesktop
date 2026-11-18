package com.pesstudios.vaultquick.core

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Denní poznámka podle nastavení Periodic Notes / Daily Notes. */
object DailyNote {
    /** [locale] – jazyk názvů dnů a měsíců (`dddd`, `MMMM`…), jako Obsidian podle svého jazyka. */
    class Location(val folder: String, val format: String, val locale: Locale = CS)

    /**
     * Umístění z obsahu `.obsidian/plugins/periodic-notes/data.json` (přednost, je-li denní
     * poznámka zapnutá) nebo `.obsidian/daily-notes.json`. Chybějící / rozbité → kořen, `YYYY-MM-DD`.
     * Jazyk Obsidianu ve vaultu uložený není – volající předá odhad ([locale]).
     */
    fun parseLocation(periodicJson: String?, coreJson: String?, locale: Locale = CS): Location {
        try {
            if (periodicJson != null) {
                val periodic = org.json.JSONObject(periodicJson)
                // Periodic Notes ≥ 1.0: nastavení v "calendarSets", aktivní sada podle "activeCalendarSet".
                val sets = periodic.optJSONArray("calendarSets")
                val active = sets?.let { a ->
                    val all = (0 until a.length()).map { a.getJSONObject(it) }
                    all.firstOrNull { it.optString("id") == periodic.optString("activeCalendarSet") } ?: all.firstOrNull()
                }
                val daily = active?.optJSONObject("day") ?: periodic.optJSONObject("daily")
                if (daily != null && daily.optBoolean("enabled", true)) {
                    return Location(daily.optString("folder"), daily.optString("format").ifEmpty { "YYYY-MM-DD" }, locale)
                }
            }
            if (coreJson != null) {
                val json = org.json.JSONObject(coreJson)
                return Location(json.optString("folder"), json.optString("format").ifEmpty { "YYYY-MM-DD" }, locale)
            }
        } catch (_: Exception) {
        }
        return Location("", "YYYY-MM-DD", locale)
    }

    /** Cesta k poznámce; formát i složka jsou vzory moment.js (Obsidian), názvy v jazyce [Location.locale]. */
    fun path(location: Location, date: LocalDate): String {
        val folder = format(location.folder, date, location.locale).trim('/')
        val name = format(location.format, date, location.locale) + ".md"
        return if (folder.isEmpty()) name else "$folder/$name"
    }

    private val CS = Locale.forLanguageTag("cs")
    private val TOKEN = Regex("""\[[^\]]*]|YYYY|YY|MMMM|MMM|MM|M|DD|D|dddd|ddd""")

    /** Podmnožina tokenů moment.js: `YYYY YY MMMM MMM MM M DD D dddd ddd [text]`. */
    fun format(pattern: String, date: LocalDate, locale: Locale = CS): String = TOKEN.replace(pattern) { m ->
        when (val t = m.value) {
            "YYYY" -> "%04d".format(date.year)
            "YY" -> "%02d".format(date.year % 100)
            "MMMM" -> date.format(DateTimeFormatter.ofPattern("LLLL", locale))
            "MMM" -> date.format(DateTimeFormatter.ofPattern("LLL", locale)).trimEnd('.')
            "MM" -> "%02d".format(date.monthValue)
            "M" -> date.monthValue.toString()
            "DD" -> "%02d".format(date.dayOfMonth)
            "D" -> date.dayOfMonth.toString()
            "dddd" -> date.format(DateTimeFormatter.ofPattern("EEEE", locale))
            "ddd" -> date.format(DateTimeFormatter.ofPattern("EEE", locale)).trimEnd('.')
            else -> t.substring(1, t.length - 1)
        }
    }
}
