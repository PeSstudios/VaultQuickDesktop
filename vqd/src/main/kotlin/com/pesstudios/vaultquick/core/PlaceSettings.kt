package com.pesstudios.vaultquick.core

/** Nastavení upozornění podle místa (úkoly s #místo v okolí). */
data class PlaceSettings(
    val enabled: Boolean = false,
    /** Složka ve vaultu s poznámkami míst; prázdná = podle jazyka aplikace (viz [folderFor]). */
    val folder: String = "",
    /** Po kolika hodinách se může upozornění na totéž místo opakovat. */
    val cooldownHours: Int = 3,
    /** Vlastní názvy vlastností poznámky místa; prázdné = výchozí podle jazyka. */
    val names: PlaceNames = PlaceNames(),
) {
    /** Názvy vlastností pro čtení a zápis: vlastní, jinak výchozí podle jazyka aplikace. */
    fun keysFor(language: String): PlaceKeys {
        val d = PlaceKeys.forLanguage(language)
        fun pick(custom: String, default: String) = custom.trim().ifEmpty { default }
        return d.copy(
            context = pick(names.context, d.context),
            location = pick(names.location, d.location),
            radius = pick(names.radius, d.radius),
            active = pick(names.active, d.active),
        )
    }

    /** Nastavená složka, nebo výchozí podle jazyka: `Místa` / `Places`. */
    fun folderFor(language: String): String = folder.ifBlank { PlaceKeys.forLanguage(language).folder }

    companion object {
        val COOLDOWN_OPTIONS = listOf(1, 3, 6, 12, 24)
    }
}

/** Vlastní názvy vlastností poznámky místa (jak je uživatel píše v Obsidianu); prázdný = výchozí. */
data class PlaceNames(
    val context: String = "",
    val location: String = "",
    val radius: String = "",
    val active: String = "",
)
