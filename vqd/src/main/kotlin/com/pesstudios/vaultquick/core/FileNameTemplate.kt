package com.pesstudios.vaultquick.core

import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/** Název souboru ze vzoru s tokeny `{první řádek}`, `{datum}`, `{čas}`, `{předvolba}` (i anglicky `{first line}`, `{date}`, `{time}`, `{preset}`). */
object FileNameTemplate {
    const val DEFAULT = "{první řádek}"
    private const val MAX = 80
    private val DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd")
    private val TIME = DateTimeFormatter.ofPattern("HHmm")
    private val FORBIDDEN = Regex("[\\\\:*?\"<>|#^\\[\\]]")

    fun render(template: String, firstLine: String, presetLabel: String, now: ZonedDateTime): String {
        val date = now.format(DATE)
        val time = now.format(TIME)
        val filled = template
            .replace("{první řádek}", firstLine).replace("{first line}", firstLine)
            .replace("{datum}", date).replace("{date}", date)
            .replace("{čas}", time).replace("{time}", time)
            .replace("{předvolba}", presetLabel).replace("{preset}", presetLabel)
        return clean(filled).ifEmpty { clean("$presetLabel $date $time") }
    }

    /** Bez znaků, které Obsidian/Android v názvu nesnese; max 80 znaků (na hranici slova). */
    fun clean(text: String): String {
        val c = text.replace('/', '-').replace(FORBIDDEN, " ")
            .replace(Regex("\\s+"), " ").trim().trimEnd('.').trim()
            // Tečka na začátku = skrytý soubor, který Obsidian neukáže.
            .trimStart('.').trim()
        // Jen pomlčky a mezery (např. z "///") nejsou použitelný název.
        if (c.all { it == '-' || it == ' ' }) return ""
        return if (c.length <= MAX) c else c.take(MAX).substringBeforeLast(' ').ifEmpty { c.take(MAX) }.trim()
    }
}
