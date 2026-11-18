package com.pesstudios.vaultquick.core

/**
 * Názvy vlastností poznámky místa. Zapisuje se pod těmito názvy; čtou se tyto, a když v poznámce
 * nejsou, i výchozí česká a anglická varianta (viz [candidates]).
 */
data class PlaceKeys(val context: String, val location: String, val radius: String, val active: String, val tag: String, val folder: String) {
    /** Názvy ke čtení v pořadí přednosti: tyto, pak české, pak anglické. */
    fun candidates(of: (PlaceKeys) -> String): List<String> = listOf(this, CS, EN).map(of).distinct()

    companion object {
        val CS = PlaceKeys("kontext", "poloha", "okruh", "aktivni", "misto", "Místa")
        val EN = PlaceKeys("context", "location", "radius", "active", "place", "Places")

        fun forLanguage(language: String): PlaceKeys = if (language == "cs") CS else EN
    }
}

/** Zápis poznámky místa; vždy blokové seznamy (inline seznam by se dělil na čárce v souřadnicích). */
object PlaceEdits {
    fun create(context: String, point: GeoPoint, radius: Int, keys: PlaceKeys = PlaceKeys.CS): String = buildString {
        append("---\n")
        append(keys.context).append(": ").append(NoteFormat.yaml(context)).append('\n')
        append(keys.location).append(":\n  - ").append(NoteFormat.yaml(GeoInput.format(point))).append('\n')
        append(keys.radius).append(": ").append(radius.coerceIn(Places.MIN_RADIUS, Places.MAX_RADIUS)).append('\n')
        append("tags:\n  - ").append(keys.tag).append('\n')
        append("---\n")
    }

    /** Další poloha (pobočka) pod tu vlastnost, kterou poznámka už používá; jinak [keys]. */
    fun addPoint(text: String, point: GeoPoint, keys: PlaceKeys = PlaceKeys.CS): String {
        val fm = Frontmatter.parse(text)
        val key = keys.candidates { it.location }.firstOrNull { it in fm } ?: keys.location
        return Frontmatter.addListItem(text, key, NoteFormat.yaml(GeoInput.format(point)))
    }
}
