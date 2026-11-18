package com.pesstudios.vaultquick.core

/** Kontexty nabízené v editoru úkolu. */
object Contexts {
    /**
     * Známé kontexty: nejdřív ty z úkolů podle četnosti (při shodě podle prvního výskytu),
     * pak kontexty míst, které ještě nejsou. Duplicity (bez `@`, diakritiky, velikosti písmen)
     * se sloučí a zůstane první zápis.
     */
    fun known(tasks: List<Task>, places: List<Place>): List<String> {
        val first = LinkedHashMap<String, String>()
        val count = HashMap<String, Int>()
        for (t in tasks) for (c in t.contexts) {
            val shown = c.trim().removePrefix("@")
            val key = Places.normalizeContext(shown)
            if (key.isEmpty()) continue
            first.putIfAbsent(key, shown)
            count[key] = (count[key] ?: 0) + 1
        }
        val fromTasks = first.keys.sortedByDescending { count[it] }.map { first.getValue(it) }
        val seen = first.keys.toMutableSet()
        val fromPlaces = places.flatMap { it.contexts }.filter { seen.add(Places.normalizeContext(it)) }
        return fromTasks + fromPlaces.map { it.trim().removePrefix("@") }
    }
}
