package com.pesstudios.vaultquick.core

import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalDateTime

/** Poslední spočítaný seznam pro widget. */
data class UpcomingSnapshot(
    val computedAt: LocalDateTime,
    val items: List<UpcomingItem>,
    /** Varování pro widget (např. nedostupný vault); null = v pořádku. */
    val warning: String?,
)

object SnapshotJson {
    fun toJson(s: UpcomingSnapshot): String = JSONObject()
        .put("computedAt", s.computedAt.toString())
        .put("warning", s.warning ?: JSONObject.NULL)
        .put("items", JSONArray(s.items.map { i ->
            JSONObject()
                .put("kind", i.kind.name).put("name", i.name).put("type", i.type)
                .put("date", i.date.toString()).put("daysUntil", i.daysUntil)
                .put("ordinal", i.ordinal ?: JSONObject.NULL)
                .put("place", i.place).put("label", i.label)
                .put("source", when (val src = i.source) {
                    is ItemSource.Note -> JSONObject().put("note", src.path)
                    is ItemSource.Contact -> JSONObject().put("contactId", src.id).put("lookupKey", src.lookupKey)
                })
        }))
        .toString()

    fun fromJson(text: String): UpcomingSnapshot? = runCatching {
        val o = JSONObject(text)
        val items = o.getJSONArray("items")
        UpcomingSnapshot(
            computedAt = LocalDateTime.parse(o.getString("computedAt")),
            items = (0 until items.length()).map { n ->
                val i = items.getJSONObject(n)
                val src = i.getJSONObject("source")
                UpcomingItem(
                    kind = UpcomingKind.valueOf(i.getString("kind")),
                    name = i.getString("name"),
                    type = i.getString("type"),
                    date = LocalDate.parse(i.getString("date")),
                    daysUntil = i.getInt("daysUntil"),
                    ordinal = if (i.isNull("ordinal")) null else i.getInt("ordinal"),
                    place = i.optString("place"),
                    label = i.optString("label"),
                    source = if (src.has("note")) ItemSource.Note(src.getString("note"))
                    else ItemSource.Contact(src.getLong("contactId"), src.getString("lookupKey")),
                )
            },
            warning = if (o.isNull("warning")) null else o.getString("warning"),
        )
    }.getOrNull()
}

object UpcomingView {
    /**
     * Položky snímku přepočítané k [today]: snímek může být z předchozího dne (přepočet po
     * půlnoci nemusí proběhnout hned), proto se "za N dní" počítá až při vykreslení.
     */
    fun visible(items: List<UpcomingItem>, today: LocalDate, daysAhead: Int): List<UpcomingItem> = items
        .map { it.copy(daysUntil = java.time.temporal.ChronoUnit.DAYS.between(today, it.date).toInt()) }
        .filter { it.daysUntil in 0..daysAhead }
}
