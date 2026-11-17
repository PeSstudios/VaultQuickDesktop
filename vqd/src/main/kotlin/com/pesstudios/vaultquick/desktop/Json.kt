package com.pesstudios.vaultquick.desktop

import com.pesstudios.vaultquick.core.AgendaEntry
import com.pesstudios.vaultquick.core.TaskNotesSettings
import java.time.format.DateTimeFormatter
import org.json.JSONArray
import org.json.JSONObject

/** Převod položek agendy na JSON podle protokolu `vqd`. */
object Json {
    private val timeFormat = DateTimeFormatter.ofPattern("HH:mm")

    fun entry(e: AgendaEntry): JSONObject = JSONObject()
        .put("path", e.task.path)
        .put("title", e.task.title)
        .put("date", e.date?.toString() ?: JSONObject.NULL)
        .put("time", e.time?.format(timeFormat) ?: JSONObject.NULL)
        .put("checkable", e.checkable)
        .put("occurrence", e.occurrence)
        .put("completable", e.completable)
        .put("status", e.task.status)
        .put("priority", e.task.priority)
        .put("projects", JSONArray(e.task.projects))

    fun entries(list: List<AgendaEntry>): JSONArray = JSONArray().also { a -> list.forEach { a.put(entry(it)) } }

    /** Priority podle váhy sestupně (stabilní řazení). */
    fun prioritiesByWeight(s: TaskNotesSettings): List<String> =
        s.priorityWeights.entries.sortedByDescending { it.value }.map { it.key }
}
