package com.pesstudios.vaultquick.core

/** Pořadí jména v názvu poznámky: "Příjmení Jméno" / "Jméno Příjmení". */
enum class NameOrder { SURNAME_FIRST, GIVEN_FIRST }

data class PersonName(val given: String, val family: String) {
    /** Klíč pro párování osob (vault × kontakty): nezáleží na pořadí, velikosti písmen ani diakritice. */
    val key: String?
        get() {
            if (given.isBlank() || family.isBlank()) return null
            return listOf(normalize(given.trim()), normalize(family.trim())).sorted().joinToString("|")
        }
}

object PersonNames {
    /** Tituly bez tečky (slova s tečkou se za tituly považují vždy – jméno tečku nemá). */
    private val TITLES = setOf(
        "bc", "bca", "ing", "arch", "mgr", "mga", "mudr", "mddr", "mvdr", "judr", "phdr", "rndr",
        "pharmdr", "thdr", "paeddr", "thlic", "dr", "doc", "prof", "phd", "csc", "drsc", "dis",
        "mba", "msc", "llm", "artd", "thd",
    )

    fun parse(text: String, order: NameOrder): PersonName {
        val words = text.substringBefore(',').trim().split(Regex("\\s+"))
            .filter { it.isNotEmpty() && !isTitle(it) }
        return when (words.size) {
            0 -> PersonName("", "")
            1 -> PersonName(words[0], "")
            else -> when (order) {
                NameOrder.SURNAME_FIRST -> PersonName(words.last(), words.dropLast(1).joinToString(" "))
                NameOrder.GIVEN_FIRST -> PersonName(words.first(), words.drop(1).joinToString(" "))
            }
        }
    }

    private fun isTitle(word: String) = '.' in word || normalize(word) in TITLES
}
