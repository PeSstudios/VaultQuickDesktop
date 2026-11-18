package com.pesstudios.vaultquick.core

/** Úpravy stránky, ke které se přiřazuje zachycený záznam. */
object PageEdits {
    private val HEADING = Regex("^(#{1,6})\\s+(.*?)\\s*#*\\s*$")

    /** Název nadpisu bez úvodního emoji – „💡 Nápady“ najde i „## Nápady“ a naopak. */
    private fun key(heading: String) = heading.trim().trimStart { !it.isLetterOrDigit() }.lowercase()

    /**
     * Připíše [entry] na konec sekce `## heading` (podnadpisy patří do sekce); chybějící sekci založí
     * na konci. Nadpis se hledá bez ohledu na velikost písmen a úvodní emoji.
     */
    fun appendToSection(text: String, heading: String, entry: String): String {
        val lines = text.split("\n").toMutableList()
        val idx = lines.indexOfFirst { line -> HEADING.matchEntire(line.trim())?.groupValues?.get(2)?.let(::key) == key(heading) }
        if (idx < 0) {
            val body = text.trimEnd('\n')
            return (if (body.isEmpty()) "" else "$body\n\n") + "## $heading\n$entry\n"
        }
        val level = HEADING.matchEntire(lines[idx].trim())!!.groupValues[1].length
        var end = (idx + 1 until lines.size).firstOrNull { i ->
            HEADING.matchEntire(lines[i].trim())?.let { it.groupValues[1].length <= level } == true
        } ?: lines.size
        while (end > idx + 1 && lines[end - 1].isBlank()) end--
        lines.add(end, entry)
        return lines.joinToString("\n")
    }
}
