package com.pesstudios.vaultquick.core

import java.time.LocalDate

data class GeoPoint(val lat: Double, val lng: Double)

/** Problém s polohou místa; text k němu dodá UI. */
enum class PlaceProblem { NO_VALID_POINT, SOME_POINTS_INVALID }

/** Poznámka místa ve vaultu (`kontext`, `poloha`, `okruh`, `aktivni` – nebo anglicky, viz [PlaceKeys]). */
data class Place(
    val path: String,
    val name: String,
    /** Kontexty bez `@` a diakritiky (viz [Places.normalizeContext]). */
    val contexts: List<String>,
    val points: List<GeoPoint>,
    val radiusMeters: Int,
    val active: Boolean,
    val problem: PlaceProblem?,
)

object Places {
    const val DEFAULT_RADIUS = 300
    const val MIN_RADIUS = 100
    const val MAX_RADIUS = 2000

    /** Kontext pro porovnání: bez `@`, bez diakritiky, malými písmeny. */
    fun normalizeContext(value: String): String = normalize(value.trim().removePrefix("@"))

    /** null = poznámka není místo (chybí vlastnost kontextu). */
    fun parse(path: String, text: String, keys: PlaceKeys = PlaceKeys.CS): Place? {
        val fm = Frontmatter.parse(text)
        // Názvy z nastavení mají přednost, pak česká a anglická výchozí.
        fun key(of: (PlaceKeys) -> String) = keys.candidates(of).firstOrNull { it in fm } ?: of(keys)
        val contexts = fm.list(key { it.context }).map(::normalizeContext).filter { it.isNotEmpty() }.distinct()
        if (contexts.isEmpty()) return null
        val raw = fm.list(key { it.location }).filter { it.isNotBlank() }
        val points = raw.mapNotNull(GeoInput::parse)
        return Place(
            path = path,
            name = path.substringAfterLast('/').removeSuffix(".md"),
            contexts = contexts,
            points = points,
            radiusMeters = (fm.str(key { it.radius })?.trim()?.toIntOrNull() ?: DEFAULT_RADIUS).coerceIn(MIN_RADIUS, MAX_RADIUS),
            active = fm.str(key { it.active })?.trim()?.lowercase() != "false",
            problem = when {
                points.isEmpty() -> PlaceProblem.NO_VALID_POINT
                points.size < raw.size -> PlaceProblem.SOME_POINTS_INVALID
                else -> null
            },
        )
    }

    /**
     * Úkoly patřící k místu: shoduje se kontext, úkol je nesplněný a není naplánovaný
     * (`scheduled`) na později než [today]; `due` v budoucnu nevadí. Pořadí: priorita, název.
     */
    fun tasksFor(place: Place, tasks: List<Task>, s: TaskNotesSettings, today: LocalDate): List<Task> {
        val wanted = place.contexts.toSet()
        return tasks
            .filter { t -> TaskNotes.isPending(t, s) && !(t.scheduledDate?.isAfter(today) ?: false) && t.contexts.any { normalizeContext(it) in wanted } }
            .sortedWith(compareByDescending<Task> { s.priorityWeights[it.priority] ?: 0 }.thenBy { it.title })
    }
}
