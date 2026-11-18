package com.pesstudios.vaultquick.core

/** Typ výročí: emoji pro zobrazení a složka, kam se zakládá nová poznámka. */
data class AnniversaryType(val name: String, val emoji: String, val newNoteFolder: String)

/** Jak jsou výročí zapsaná ve vaultu: `- #výročí [typ:: …] [datum:: …] [popisek:: …] [misto:: …]`. */
data class AnniversarySettings(
    val keyword: String = "#výročí",
    val typeField: String = "typ",
    val dateField: String = "datum",
    val placeField: String = "misto",
    val labelField: String = "popisek",
    /** Složka nabízená přednostně při výběru poznámky; "" = kořen vaultu. */
    val peopleFolder: String = "",
    /** Pořadí jména v názvech poznámek lidí – pro svátky a párování s kontakty. */
    val nameOrder: NameOrder = NameOrder.SURNAME_FIRST,
    /** Vlastní kalendář svátků (relativní cesta s .md); "" = vestavěný český. */
    val nameDaysFile: String = "",
    val types: List<AnniversaryType> = DEFAULT_TYPES,
) {
    companion object {
        val DEFAULT_TYPES = listOf(
            AnniversaryType("narozeniny", "🎂", ""),
            AnniversaryType("výročí", "⭐", ""),
            AnniversaryType("úmrtí", "🕯️", ""),
            AnniversaryType("událost", "📅", ""),
            AnniversaryType("svátek", "🎊", ""),
        )
    }
}
