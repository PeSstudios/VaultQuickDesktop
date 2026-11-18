package com.pesstudios.vaultquick.core

import java.time.Instant
import java.time.LocalDate
import java.time.ZonedDateTime

/** Jeden okruh (geofence) pro systém; [id] je `cesta#index bodu`, u dlouhé cesty zkrácené (viz [GeofencePlan.fenceId]). */
data class Fence(val id: String, val point: GeoPoint, val radiusMeters: Int, val placePath: String)

object GeofencePlan {
    const val MAX_FENCES = 100

    /**
     * Okruhy všech aktivních míst s platným bodem. Při překročení [MAX_FENCES] mají přednost místa
     * s úkoly (vyšší priorita, pak bližší `due`), zbytek podle názvu; poslednímu místu se dají jen body, které se vejdou.
     */
    fun compute(places: List<Place>, tasks: List<Task>, s: TaskNotesSettings, today: LocalDate): List<Fence> {
        val weights = s.priorityWeights
        val ranked = places.filter { it.active && it.points.isNotEmpty() }.map { it to Places.tasksFor(it, tasks, s, today) }
        val withTasks = ranked.filter { it.second.isNotEmpty() }
            .sortedWith(
                compareByDescending<Pair<Place, List<Task>>> { (_, ts) -> ts.maxOf { weights[it.priority] ?: 0 } }
                    .thenBy { (_, ts) -> ts.mapNotNull { it.dueDate }.minOrNull() ?: LocalDate.MAX }
                    .thenBy { it.first.name },
            )
        val rest = ranked.filter { it.second.isEmpty() }.sortedBy { it.first.name }
        val out = ArrayList<Fence>()
        for ((p, _) in withTasks + rest) {
            for ((i, pt) in p.points.withIndex()) {
                if (out.size >= MAX_FENCES) return out
                out += Fence(fenceId(p.path, i), pt, p.radiusMeters, p.path)
            }
        }
        return out
    }

    /** Play služby přijmou id okruhu nejvýš 100 znaků dlouhé. */
    const val MAX_ID_LENGTH = 100

    /**
     * Id okruhu: `cesta#index`; je-li delší než [MAX_ID_LENGTH], pak stabilní zkrácené `h<sha-1 cesty>#index`
     * – cestu k němu je třeba si pamatovat zvlášť (viz [isShortened]).
     */
    fun fenceId(path: String, index: Int): String {
        val plain = "$path#$index"
        if (plain.length <= MAX_ID_LENGTH) return plain
        val hex = java.security.MessageDigest.getInstance("SHA-1").digest(path.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
        return "h$hex#$index"
    }

    /** Id okruhu nevzniklo z cesty přímo – [placePathOf] ho na cestu nepřevede. */
    fun isShortened(fence: Fence): Boolean = !fence.id.startsWith(fence.placePath + "#")

    /**
     * Cesta místa z id okruhu (bere se poslední `#`, cesta může `#` obsahovat). Zkrácená id
     * ([fenceId] u dlouhé cesty) se hledají v [shortened] (id → cesta).
     */
    fun placePathOf(fenceId: String, shortened: Map<String, String> = emptyMap()): String =
        shortened[fenceId] ?: fenceId.substringBeforeLast('#')
}

/** Obsah notifikace; titulek skládá Android vrstva z [placeName], [taskCount] a případně názvu jediného úkolu. */
data class PlaceAlert(
    val placeName: String,
    val taskCount: Int,
    val lines: List<String>,
    val more: Int,
    val singleTaskPath: String?,
)

object PlaceNotifications {
    const val MAX_LINES = 6

    private val OPEN_ITEM = Regex("""^\s*[-*]\s+\[ \]\s+(.*\S)\s*$""")

    fun build(place: Place, tasks: List<Task>, bodyOf: (Task) -> String?): PlaceAlert? {
        if (tasks.isEmpty()) return null
        if (tasks.size > 1) {
            return PlaceAlert(place.name, tasks.size, tasks.take(MAX_LINES).map { it.title }, (tasks.size - MAX_LINES).coerceAtLeast(0), null)
        }
        val t = tasks.first()
        val items = bodyOf(t)?.let(::openItems).orEmpty()
        val lines = if (items.isEmpty()) listOf(t.title) else items.take(MAX_LINES)
        val more = if (items.isEmpty()) 0 else (items.size - MAX_LINES).coerceAtLeast(0)
        return PlaceAlert(place.name, 1, lines, more, t.path)
    }

    /** Nesplněné položky checklistu (`- [ ] text`, `* [ ] text`) na libovolné úrovni odsazení. */
    fun openItems(body: String): List<String> =
        body.lineSequence().mapNotNull { OPEN_ITEM.matchEntire(it)?.groupValues?.get(1)?.trim() }.toList()
}

object PlaceCooldown {
    /** Upozornit, pokud místo není ztlumené a od posledního upozornění uplynul interval. */
    fun shouldNotify(now: Instant, lastShown: Instant?, mutedUntil: Instant?, cooldownHours: Int): Boolean {
        if (mutedUntil != null && now.isBefore(mutedUntil)) return false
        if (lastShown != null && now.isBefore(lastShown.plusSeconds(cooldownHours * 3600L))) return false
        return true
    }

    /** Ztlumení do nejbližší půlnoci (v časové zóně [now]). */
    fun muteUntil(now: ZonedDateTime): Instant =
        now.toLocalDate().plusDays(1).atStartOfDay(now.zone).toInstant()
}
