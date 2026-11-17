package com.pesstudios.vaultquick.desktop

import com.pesstudios.vaultquick.core.Agendas
import java.time.LocalDate
import java.time.ZonedDateTime
import org.json.JSONArray
import org.json.JSONObject

/** Přepsání předvolby nového úkolu z `config.json` (používají zapisovací příkazy). */
data class TaskPresetOverride(val folder: String?, val fileNameTemplate: String?, val tags: List<String>?)

data class DesktopConfig(val taskPreset: TaskPresetOverride? = null)

/** Chyba příkazu s kódem protokolu. */
class CommandException(val code: String, message: String) : Exception(message)

/** Jediné místo, kde se požadavky protokolu `vqd` zpracovávají; [handle] nikdy nevyhazuje. */
class Commands(val vault: Vault, val config: DesktopConfig, val clock: () -> ZonedDateTime) {

    fun handle(req: JSONObject): JSONObject {
        val id = req.opt("id")
        return try {
            val cmd = req.optString("cmd", "")
            if (!vault.available()) throw CommandException("vault", "Vault není dostupný: ${vault.root}")
            val result = when (cmd) {
                "agenda" -> agenda(req)
                "meta" -> meta()
                else -> throw CommandException("bad_request", "Neznámý příkaz: '$cmd'")
            }
            JSONObject().put("id", id ?: JSONObject.NULL).put("ok", true).put("result", result)
        } catch (e: CommandException) {
            error(id, e.code, e.message ?: "")
        } catch (e: Throwable) {
            error(id, "failed", e.message ?: e.toString())
        }
    }

    private fun error(id: Any?, code: String, message: String): JSONObject =
        JSONObject().put("id", id ?: JSONObject.NULL).put("ok", false).put("error", code).put("message", message)

    private fun today(req: JSONObject): LocalDate {
        val text = req.optString("today", "")
        if (text.isBlank()) return clock().toLocalDate()
        return runCatching { LocalDate.parse(text) }.getOrElse { throw CommandException("bad_request", "Neplatné datum: '$text'") }
    }

    private fun agenda(req: JSONObject): JSONObject {
        val s = vault.settings
        val today = today(req)
        val days = req.optInt("days", 7).coerceIn(1, 14)
        val project = if (req.isNull("project")) null else req.optString("project").takeIf { it.isNotBlank() }
        val noDate = req.optString("noDate", "inProgress")
        if (noDate !in setOf("none", "inProgress", "all")) throw CommandException("bad_request", "Neplatné noDate: '$noDate'")
        val view = Agendas.build(
            Agendas.ofProject(vault.tasks(), project), s, today, days,
            includeNoDate = noDate != "none", allNoDate = noDate == "all",
        )
        val todayEntries = view.days.first().entries.filter { !it.occurrence }
        return JSONObject()
            .put("overdue", Json.entries(view.overdue))
            .put("days", JSONArray().also { a ->
                view.days.forEach { d ->
                    a.put(JSONObject().put("date", d.date.toString()).put("entries", Json.entries(d.entries)))
                }
            })
            .put("noDate", Json.entries(view.noDate))
            .put("counts", JSONObject().put("today", todayEntries.size).put("overdue", view.overdue.size))
            .put("top", JSONArray(todayEntries.take(3).map { it.task.title }))
    }

    private fun meta(): JSONObject {
        val s = vault.settings
        return JSONObject()
            .put("projects", JSONArray(Agendas.projects(vault.tasks(), s)))
            .put("statuses", JSONArray(s.statuses))
            .put("priorities", JSONArray(Json.prioritiesByWeight(s)))
    }
}
