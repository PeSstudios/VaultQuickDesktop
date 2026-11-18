package com.pesstudios.vaultquick.core

import java.util.Locale

/** Rozpoznání souřadnic z textu, odkazů Google Map a `geo:` URI. */
object GeoInput {
    private const val NUM = "-?\\d+(?:[.,]\\d+)?"
    private val PLAIN = Regex("^($NUM)(?:\\s*;\\s*|\\s*,\\s+|\\s+|,)($NUM)$")
    private val DATA = Regex("!3d(-?\\d+(?:\\.\\d+)?)!4d(-?\\d+(?:\\.\\d+)?)")
    private val AT = Regex("@(-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?)")
    private val QUERY = Regex("[?&](?:q|ll|query|destination|center)=(-?\\d+(?:\\.\\d+)?)(?:,|%2C)\\s*(-?\\d+(?:\\.\\d+)?)", RegexOption.IGNORE_CASE)
    private val GEO = Regex("^geo:(-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?)", RegexOption.IGNORE_CASE)

    fun parse(text: String): GeoPoint? {
        val t = text.trim()
        if (t.isEmpty()) return null
        val m = when {
            t.startsWith("geo:", ignoreCase = true) -> GEO.find(t)?.takeIf { it.groupValues[1].toDoubleOrNull() != 0.0 || it.groupValues[2].toDoubleOrNull() != 0.0 } ?: QUERY.find(t)
            t.startsWith("http", ignoreCase = true) -> if (isShortLink(t)) null else DATA.find(t) ?: AT.find(t) ?: QUERY.find(t)
            else -> PLAIN.matchEntire(t)
        } ?: return null
        val lat = m.groupValues[1].replace(',', '.').toDoubleOrNull() ?: return null
        val lng = m.groupValues[2].replace(',', '.').toDoubleOrNull() ?: return null
        if (!lat.isFinite() || !lng.isFinite() || lat !in -90.0..90.0 || lng !in -180.0..180.0) return null
        return GeoPoint(lat, lng)
    }

    /** Zkrácený odkaz (maps.app.goo.gl, goo.gl/maps) souřadnice neobsahuje, bez sítě ho nerozbalíme. */
    fun isShortLink(text: String): Boolean {
        val t = text.trim().lowercase()
        return t.contains("maps.app.goo.gl") || t.contains("goo.gl/maps")
    }

    /** `lat, lng` na 6 desetinných míst s tečkou. */
    fun format(p: GeoPoint): String = String.format(Locale.ROOT, "%.6f, %.6f", p.lat, p.lng)
}
