package com.pesstudios.vaultquick.desktop

import com.pesstudios.vaultquick.core.AgendaEntry
import com.pesstudios.vaultquick.core.Agendas
import com.pesstudios.vaultquick.core.DateChoice
import com.pesstudios.vaultquick.core.Recurrence
import com.pesstudios.vaultquick.core.Task
import com.pesstudios.vaultquick.core.TaskChanges
import com.pesstudios.vaultquick.core.TaskEdits
import com.pesstudios.vaultquick.core.TaskNotes
import com.pesstudios.vaultquick.reminders.ActionResult
import com.pesstudios.vaultquick.reminders.TaskActions
import com.pesstudios.vaultquick.vault.FileVaultStorage
import java.io.File
import java.time.LocalDate
import java.time.LocalTime
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
                "get" -> get(req)
                "save" -> save(req)
                "complete" -> complete(req)
                "archive" -> archive(req)
                "create" -> create(req)
                "icon" -> icon(req)
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

    // --- Zapisovací příkazy ---

    /** Relativní cesta úkolu z požadavku; mimo vault nebo chybějící → `bad_request`. */
    private fun pathOf(req: JSONObject): String {
        val path = req.optString("path", "").trim()
        if (path.isEmpty() || req.isNull("path")) throw CommandException("bad_request", "Chybí path")
        val root = vault.root.canonicalFile
        val target = File(root, path).canonicalFile
        if (!target.path.startsWith(root.path + File.separator)) throw CommandException("bad_request", "Cesta mimo vault: '$path'")
        return path
    }

    /** Soubor úkolu a jeho rozebraný obsah; chybějící soubor nebo ne-úkol → `missing`. */
    private fun load(path: String): Triple<File, String, Task> {
        val file = File(vault.root, path)
        if (!file.isFile) throw CommandException("missing", "Úkol neexistuje: $path")
        val text = file.readText()
        val task = TaskNotes.parseTask(path, text, vault.settings) ?: throw CommandException("missing", "Není úkol: $path")
        return Triple(file, text, task)
    }

    private fun date(text: String): LocalDate =
        runCatching { LocalDate.parse(text) }.getOrElse { throw CommandException("bad_request", "Neplatné datum: '$text'") }

    private fun time(text: String): LocalTime =
        runCatching { LocalTime.parse(text) }.getOrElse { throw CommandException("bad_request", "Neplatný čas: '$text'") }

    private fun strings(a: JSONArray?): List<String> = a?.let { (0 until it.length()).map(it::getString) }.orEmpty()

    private fun get(req: JSONObject): JSONObject {
        val path = pathOf(req)
        // mtime před čtením textu: změna mezi tím dá při `save` konflikt, ne tiché přepsání.
        val mtime = File(vault.root, path).lastModified()
        val (_, text, t) = load(path)
        // Hotovo půjde, je-li úkol běžný nebo opakování umíme spočítat (jako v agendě).
        val completable = !t.isRecurring ||
            t.scheduledDate?.let { Recurrence.next(t.recurrence!!, it, it, setOf(it)) != null } == true
        val entry = Json.entry(AgendaEntry(t, t.date, t.time, checkable = true, occurrence = false, completable = completable))
            .put("scheduled", t.scheduled ?: JSONObject.NULL)
            .put("due", t.due ?: JSONObject.NULL)
            .put("recurrence", t.recurrence ?: JSONObject.NULL)
            .put("contexts", JSONArray(t.contexts))
        return JSONObject().put("task", entry).put("body", TaskEdits.bodyOf(text)).put("mtime", mtime)
    }

    /** Uloží formulář; soubor změněný od `get` (jiné `mtime`) se nepřepíše → `conflict`. Chybějící pole = beze změny. */
    private fun save(req: JSONObject): JSONObject {
        val path = pathOf(req)
        if (!req.has("mtime")) throw CommandException("bad_request", "Chybí mtime")
        val mtime = req.optLong("mtime", -1)
        val (file, text, t) = load(path)
        // mtime až po přečtení textu: shoda znamená, že přečtený text je ta verze, kterou formulář zná.
        if (file.lastModified() != mtime) throw CommandException("conflict", "Soubor se mezitím změnil: $path")
        val c = req.optJSONObject("changes") ?: throw CommandException("bad_request", "Chybí changes")
        val changes = TaskChanges(
            title = c.optString("title", t.title).takeIf { it.isNotBlank() } ?: t.title,
            date = if (!c.has("date")) t.date else if (c.isNull("date")) null else date(c.getString("date")),
            time = if (!c.has("time")) t.time else if (c.isNull("time")) null else time(c.getString("time")),
            status = c.optString("status", t.status).ifBlank { t.status },
            priority = c.optString("priority", t.priority).ifBlank { t.priority },
            projects = if (c.has("projects")) strings(c.optJSONArray("projects")) else t.projects,
            contexts = if (c.has("contexts")) strings(c.optJSONArray("contexts")) else t.contexts,
            body = if (c.has("body") && !c.isNull("body")) c.getString("body") else TaskEdits.bodyOf(text),
        )
        FileVaultStorage(vault.root).write(path, TaskEdits.update(text, t, vault.settings, changes, clock()))
        return JSONObject().put("mtime", file.lastModified())
    }

    /** Hotovo jako `tasks/TaskCompletion.kt` v telefonu: zastaralý řádek (dvojklik, změna v Obsidianu) nic nezapíše. */
    private fun complete(req: JSONObject): JSONObject {
        val path = pathOf(req)
        val expected = if (req.isNull("expected") || !req.has("expected")) null else date(req.getString("expected"))
        val today = today(req)
        val (_, _, t) = load(path)
        if (!Agendas.stillCurrent(t, vault.settings, expected)) throw CommandException("stale", "Úkol se mezitím změnil: $path")
        // Dnešní výskyt opakovaného (i při zmeškaném scheduled) splnit jako dnešní; jinak podle scheduled.
        val instance = expected?.takeIf { it == today }
        return actionResult(TaskActions.complete(vault.root, path, instance), path)
    }

    private fun archive(req: JSONObject): JSONObject {
        val path = pathOf(req)
        return actionResult(TaskActions.archive(vault.root, path), path)
    }

    private fun actionResult(r: ActionResult, path: String): JSONObject = when (r) {
        ActionResult.OK -> JSONObject()
        ActionResult.MISSING -> throw CommandException("missing", "Úkol neexistuje: $path")
        ActionResult.FAILED -> throw CommandException("failed", "Úkol nejde zapsat: $path")
    }

    /** Nový úkol; `date` chybí = datum z textu (jako telefon), `date: null` = bez termínu. */
    private fun create(req: JSONObject): JSONObject {
        val choice = when {
            !req.has("date") -> DateChoice.FromText
            req.isNull("date") -> DateChoice.Fixed(null)
            else -> DateChoice.Fixed(date(req.getString("date")))
        }
        val project = if (req.isNull("project")) null else req.optString("project")
        val created = Create.task(vault.root, vault.settings, config.taskPreset, req.optString("text", ""), choice, project, clock())
        return JSONObject().put("path", created.path).put("project", created.project ?: JSONObject.NULL)
    }

    /** Ikona projektu z vaultu; vše nenalezené = `path: null` (ne chyba). */
    private fun icon(req: JSONObject): JSONObject {
        val project = if (req.isNull("project")) null else req.optString("project")
        return JSONObject().put("path", Icon.of(vault.root, project) ?: JSONObject.NULL)
    }
}
