package com.pesstudios.vaultquick.desktop

import com.pesstudios.vaultquick.core.DailyNote
import com.pesstudios.vaultquick.core.DateChoice
import com.pesstudios.vaultquick.core.Kind
import com.pesstudios.vaultquick.core.NoteWriter
import com.pesstudios.vaultquick.core.ProjectRef
import com.pesstudios.vaultquick.core.Presets
import com.pesstudios.vaultquick.core.TaskEdits
import com.pesstudios.vaultquick.core.TaskNotesSettings
import com.pesstudios.vaultquick.vault.FileVaultStorage
import java.io.File
import java.nio.file.Files
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class WriteCommandsTest {
    private lateinit var dir: File
    private lateinit var vault: Vault
    private val now = ZonedDateTime.of(2026, 11, 17, 9, 30, 0, 0, ZoneId.of("Europe/Prague"))

    /** Hotovo zapisuje sdílené `TaskActions` se skutečným časem – „dnes“ v testech hotova je proto skutečný den. */
    private val realToday = LocalDate.now()

    @Before fun setUp() {
        dir = Files.createTempDirectory("vqd").toFile()
        vault = Vault(File(dir, "vault").also { it.mkdirs() }, File(dir, "cache.json"))
    }

    @After fun tearDown() { dir.deleteRecursively() }

    private fun commands(config: DesktopConfig = DesktopConfig()) = Commands(vault, config) { now }

    private fun file(path: String) = File(vault.root, path)

    private fun task(name: String, vararg lines: String, body: String = ""): File {
        val f = file("TaskNotes/$name.md")
        f.parentFile.mkdirs()
        f.writeText("---\ntitle: $name\ntags:\n  - task\n${lines.joinToString("\n")}\n---\n$body")
        return f
    }

    private fun call(cmd: String, vararg params: Pair<String, Any?>, config: DesktopConfig = DesktopConfig()): JSONObject {
        val req = JSONObject().put("id", 7).put("cmd", cmd)
        params.forEach { (k, v) -> req.put(k, v ?: JSONObject.NULL) }
        return commands(config).handle(req)
    }

    private fun result(r: JSONObject): JSONObject {
        assertTrue(r.toString(), r.getBoolean("ok"))
        return r.getJSONObject("result")
    }

    private fun assertError(code: String, r: JSONObject) {
        assertFalse(r.toString(), r.getBoolean("ok"))
        assertEquals(r.toString(), code, r.getString("error"))
    }

    private fun tasksFolder(folder: String) {
        file(".obsidian/plugins/tasknotes/data.json").also { it.parentFile.mkdirs() }
            .writeText("""{"tasksFolder":"$folder"}""")
    }

    // --- get ---

    @Test fun getReturnsBodyAndMtime() {
        val f = task("Úkol", "status: open", "priority: high", "scheduled: 2026-11-18T10:00", "due: 2026-11-20",
            "contexts:", "  - doma", body = "\nPoznámka k úkolu\n")
        val r = result(call("get", "path" to "TaskNotes/Úkol.md"))
        assertEquals("Poznámka k úkolu", r.getString("body"))
        assertEquals(TaskEdits.bodyOf(f.readText()), r.getString("body"))
        assertEquals(f.lastModified(), r.getLong("mtime"))
        val t = r.getJSONObject("task")
        assertEquals("TaskNotes/Úkol.md", t.getString("path"))
        assertEquals("Úkol", t.getString("title"))
        assertEquals("2026-11-18", t.getString("date"))
        assertEquals("10:00", t.getString("time"))
        assertEquals("high", t.getString("priority"))
        assertEquals("2026-11-18T10:00", t.getString("scheduled"))
        assertEquals("2026-11-20", t.getString("due"))
        assertTrue(t.isNull("recurrence"))
        assertEquals("[\"doma\"]", t.getJSONArray("contexts").toString())
    }

    @Test fun getMissingFile() {
        assertError("missing", call("get", "path" to "TaskNotes/nic.md"))
    }

    // --- save ---

    private fun changes(vararg fields: Pair<String, Any?>) = JSONObject().also { c -> fields.forEach { (k, v) -> c.put(k, v ?: JSONObject.NULL) } }

    @Test fun saveChangesTitleAndKeepsRest() {
        val f = task("Starý", "status: open", "priority: normal", "scheduled: 2026-11-18", "dateModified: 2026-11-01T08:00:00.000+01:00",
            "vlastni: hodnota", body = "Text\n")
        val before = f.readText().lines()
        val c = changes("title" to "Nový název", "date" to "2026-11-18", "time" to null, "status" to "open",
            "priority" to "normal", "projects" to JSONArray(), "contexts" to JSONArray(), "body" to "Text")
        val r = result(call("save", "path" to "TaskNotes/Starý.md", "mtime" to f.lastModified(), "changes" to c))
        val after = f.readText().lines()
        assertTrue(after.contains("title: Nový název"))
        assertTrue(after.single { it.startsWith("dateModified:") }.startsWith("dateModified: 2026-11-17T09:30"))
        // Ostatní řádky beze změny.
        assertEquals(before.filterNot { it.startsWith("title:") || it.startsWith("dateModified:") },
            after.filterNot { it.startsWith("title:") || it.startsWith("dateModified:") })
        assertEquals(f.lastModified(), r.getLong("mtime"))
    }

    @Test fun saveConflictWhenFileChanged() {
        val f = task("Úkol", "status: open")
        val before = f.readText()
        val c = changes("title" to "Jiný", "date" to null, "time" to null, "status" to "open", "priority" to "normal",
            "projects" to JSONArray(), "contexts" to JSONArray(), "body" to "")
        assertError("conflict", call("save", "path" to "TaskNotes/Úkol.md", "mtime" to f.lastModified() - 1, "changes" to c))
        assertEquals(before, f.readText())
    }

    // --- complete ---

    @Test fun completeRegularTask() {
        val f = task("Běžný", "status: open", "scheduled: 2026-11-17")
        result(call("complete", "path" to "TaskNotes/Běžný.md", "expected" to "2026-11-17", "today" to realToday.toString()))
        val lines = f.readText().lines()
        assertTrue(lines.contains("status: done"))
        assertTrue(lines.contains("completedDate: $realToday"))
    }

    @Test fun completeRecurringTodayUsesInstance() {
        val f = task("Denně", "status: open", "scheduled: $realToday", "recurrence: FREQ=DAILY")
        result(call("complete", "path" to "TaskNotes/Denně.md", "expected" to realToday.toString(), "today" to realToday.toString()))
        val text = f.readText()
        assertTrue(text, text.contains("complete_instances:\n  - $realToday"))
        assertTrue(text, text.lines().contains("scheduled: ${realToday.plusDays(1)}"))
    }

    @Test fun completeStaleDoesNothing() {
        val f = task("Denně", "status: open", "scheduled: $realToday", "recurrence: FREQ=DAILY")
        val req = arrayOf("path" to "TaskNotes/Denně.md", "expected" to realToday.toString(), "today" to realToday.toString())
        result(call("complete", *req))
        val afterFirst = f.readText()
        assertError("stale", call("complete", *req))
        assertEquals(afterFirst, f.readText())
    }

    @Test fun completeUnsupportedRecurrenceFails() {
        task("Divný", "status: open", "scheduled: $realToday", "recurrence: FREQ=DAILY;BYSETPOS=1")
        assertError("failed", call("complete", "path" to "TaskNotes/Divný.md", "expected" to realToday.toString(), "today" to realToday.toString()))
    }

    @Test fun completeMissingFile() {
        assertError("missing", call("complete", "path" to "TaskNotes/nic.md", "expected" to null, "today" to realToday.toString()))
    }

    // --- archive ---

    @Test fun archiveAddsArchivedTag() {
        val f = task("Pryč", "status: open")
        result(call("archive", "path" to "TaskNotes/Pryč.md"))
        assertTrue(f.readText(), f.readText().contains("tags:\n  - task\n  - archived"))
    }

    // --- create ---

    @Test fun createSameAsPhone() {
        tasksFolder("0 vyřídit")
        file("projekty/pesstudios.md").also { it.parentFile.mkdirs() }.writeText("# PeS\n")
        val r = result(call("create", "text" to "Koupit mléko", "date" to "2026-11-18", "project" to "pesstudios"))
        assertEquals("0 vyřídit/Koupit mléko.md", r.getString("path"))
        assertEquals("pesstudios", r.getString("project"))

        // Totéž jádrem (jako telefon) do druhého vaultu se stejnou stránkou projektu.
        val other = File(dir, "other").also { File(it, "projekty").mkdirs() }
        File(other, "projekty/pesstudios.md").writeText("# PeS\n")
        val s = TaskNotesSettings(tasksFolder = "0 vyřídit")
        val preset = Presets.defaults("0 vyřídit").first { it.kind == Kind.TASK }
        val path = NoteWriter(FileVaultStorage(other), s, DailyNote.parseLocation(null, null))
            .save(preset, "Koupit mléko", now, DateChoice.Fixed(LocalDate.of(2026, 11, 18)), ProjectRef("projekty/pesstudios.md"))
        assertEquals(path, r.getString("path"))
        assertEquals(File(other, path).readText(), file(path).readText())
        assertTrue(file(path).readText().contains("projects:\n  - \"[[pesstudios]]\""))
    }

    @Test fun createWithMissingProjectPageSavesWithoutProject() {
        val r = result(call("create", "text" to "Něco", "date" to null, "project" to "smazaný"))
        // Uloží se bez projektu (jako telefon) a odpověď to applet dá vědět: `project` = null.
        assertTrue(r.toString(), r.has("project") && r.isNull("project"))
        val text = file(r.getString("path")).readText()
        assertFalse(text, text.contains("projects:"))
        assertFalse(text, text.contains("scheduled:"))
    }

    @Test fun createUsesPresetOverride() {
        val config = DesktopConfig(TaskPresetOverride(folder = "Inbox", fileNameTemplate = null, tags = listOf("pc")))
        val r = result(call("create", "text" to "Z počítače", "date" to null, "project" to null, config = config))
        assertEquals("Inbox/Z počítače.md", r.getString("path"))
        assertTrue(r.isNull("project"))
        assertTrue(file(r.getString("path")).readText().contains("tags:\n  - task\n  - pc\n"))
    }

    @Test fun createReportsActualProjectPageName() {
        file("projekty/PeS studios.md").also { it.parentFile.mkdirs() }.writeText("# PeS\n")
        val r = result(call("create", "text" to "Úkol", "date" to null, "project" to "pes STUDIOS"))
        assertEquals("PeS studios", r.getString("project"))
    }

    @Test fun createEmptyText() {
        assertError("empty", call("create", "text" to "   ", "date" to null, "project" to null))
    }
}
