package com.pesstudios.vaultquick.desktop

import java.io.File
import java.nio.file.Files
import java.time.ZoneId
import java.time.ZonedDateTime
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AgendaCommandTest {
    private lateinit var dir: File
    private lateinit var vault: Vault
    private lateinit var commands: Commands

    @Before fun setUp() {
        dir = Files.createTempDirectory("vqd").toFile()
        vault = Vault(File(dir, "vault").also { it.mkdirs() }, File(dir, "cache.json"))
        commands = Commands(vault, DesktopConfig()) { ZonedDateTime.of(2026, 11, 17, 9, 0, 0, 0, ZoneId.of("Europe/Prague")) }
    }

    @After fun tearDown() { dir.deleteRecursively() }

    private fun task(name: String, vararg lines: String) {
        val f = File(vault.root, "TaskNotes/$name.md")
        f.parentFile.mkdirs()
        f.writeText("---\ntitle: $name\ntags:\n  - task\n${lines.joinToString("\n")}\n---\n")
    }

    private fun agenda(vararg extra: Pair<String, Any?>): JSONObject {
        val req = JSONObject().put("id", 1).put("cmd", "agenda").put("today", "2026-11-17")
        extra.forEach { (k, v) -> req.put(k, v ?: JSONObject.NULL) }
        return commands.handle(req)
    }

    private fun result(r: JSONObject): JSONObject {
        assertTrue(r.toString(), r.getBoolean("ok"))
        return r.getJSONObject("result")
    }

    @Test fun agendaAllShowsDaysAndCounts() {
        task("Dnešní", "status: open", "scheduled: 2026-11-17")
        task("Zpožděný", "status: open", "scheduled: 2026-11-15")
        val r = result(agenda("days" to 3, "noDate" to "none"))
        val days = r.getJSONArray("days")
        assertEquals(3, days.length())
        assertEquals("2026-11-17", days.getJSONObject(0).getString("date"))
        assertEquals(1, r.getJSONObject("counts").getInt("today"))
        assertEquals(1, r.getJSONObject("counts").getInt("overdue"))
        assertEquals("Dnešní", r.getJSONArray("top").getString(0))
        assertEquals(1, r.getJSONObject("counts").getInt("overdue"))
    }

    @Test fun agendaFiltersProjectCaseInsensitive() {
        task("A", "status: open", "scheduled: 2026-11-17", "projects:", "  - \"[[pesstudios]]\"")
        task("B", "status: open", "scheduled: 2026-11-17")
        val r = result(agenda("project" to "PeSstudios", "days" to 1, "noDate" to "none"))
        val entries = r.getJSONArray("days").getJSONObject(0).getJSONArray("entries")
        assertEquals(1, entries.length())
        assertEquals("A", entries.getJSONObject(0).getString("title"))
    }

    @Test fun laterListsTasksAfterLastDay() {
        task("V rozsahu", "status: open", "scheduled: 2026-11-19")
        task("Za týden", "status: open", "scheduled: 2026-11-24")
        task("Za rok", "status: open", "due: 2027-11-01")
        task("Hotový", "status: done", "scheduled: 2026-11-25")
        task("Týdně", "status: open", "scheduled: 2026-11-26", "recurrence: FREQ=WEEKLY")
        task("Denně", "status: open", "scheduled: 2026-11-17", "recurrence: FREQ=DAILY")
        val r = result(agenda("days" to 3, "noDate" to "none", "later" to true))
        val later = r.getJSONArray("later")
        val titles = (0 until later.length()).map { later.getJSONObject(it).getString("title") }
        // každý úkol jednou s nejbližším termínem po posledním dni; výskyty „Denně“ v Dalších dnech nejsou
        assertEquals(listOf("Za týden", "Týdně", "Za rok"), titles)
        assertEquals("2026-11-24", later.getJSONObject(0).getString("date"))
        assertTrue(later.getJSONObject(1).getBoolean("checkable"))
        assertEquals("2027-11-01", later.getJSONObject(2).getString("date"))
        // bez `later` se sekce nepočítá
        assertFalse(result(agenda("days" to 3, "noDate" to "none")).has("later"))
    }

    @Test fun noDateModes() {
        task("A", "status: open")
        task("B", "status: in-progress")
        fun titles(mode: String): List<String> {
            val a = result(agenda("days" to 1, "noDate" to mode)).getJSONArray("noDate")
            return (0 until a.length()).map { a.getJSONObject(it).getString("title") }
        }
        assertEquals(emptyList<String>(), titles("none"))
        assertEquals(listOf("B"), titles("inProgress"))
        assertEquals(listOf("B", "A"), titles("all"))
    }

    @Test fun unknownProjectGivesEmptyAgenda() {
        task("A", "status: open", "scheduled: 2026-11-17")
        val r = result(agenda("project" to "neexistuje", "days" to 2, "noDate" to "all"))
        assertEquals(0, r.getJSONArray("overdue").length())
        assertEquals(0, r.getJSONArray("noDate").length())
        assertEquals(0, r.getJSONArray("days").getJSONObject(0).getJSONArray("entries").length())
        assertEquals(0, r.getJSONObject("counts").getInt("today"))
    }

    @Test fun recurringOccurrenceFlags() {
        task("Denně", "status: open", "scheduled: 2026-11-17", "recurrence: FREQ=DAILY")
        val r = result(agenda("days" to 2, "noDate" to "none"))
        val days = r.getJSONArray("days")
        val today = days.getJSONObject(0).getJSONArray("entries").getJSONObject(0)
        val tomorrow = days.getJSONObject(1).getJSONArray("entries").getJSONObject(0)
        assertTrue(today.getBoolean("checkable")); assertFalse(today.getBoolean("occurrence"))
        assertTrue(tomorrow.getBoolean("occurrence")); assertFalse(tomorrow.getBoolean("checkable"))
        assertEquals(1, r.getJSONObject("counts").getInt("today"))
    }

    @Test fun metaListsProjectsStatusesPriorities() {
        File(vault.root, ".obsidian/plugins/tasknotes/data.json").also { it.parentFile.mkdirs() }.writeText(
            """{"customStatuses":[{"value":"open"},{"value":"done","isCompleted":true}],
               "customPriorities":[{"value":"low","weight":1},{"value":"high","weight":3},{"value":"normal","weight":2}]}""",
        )
        task("A", "status: open", "projects:", "  - \"[[Zeta]]\"", "  - \"[[alfa]]\"")
        val r = result(commands.handle(JSONObject().put("id", 2).put("cmd", "meta")))
        assertEquals("[\"alfa\",\"Zeta\"]", r.getJSONArray("projects").toString())
        assertEquals("[\"open\",\"done\"]", r.getJSONArray("statuses").toString())
        assertEquals("[\"high\",\"normal\",\"low\"]", r.getJSONArray("priorities").toString())
    }

    @Test fun vaultMissingGivesVaultError() {
        val c = Commands(Vault(File(dir, "nic"), File(dir, "c")), DesktopConfig()) { ZonedDateTime.now() }
        val r = c.handle(JSONObject().put("id", 3).put("cmd", "meta"))
        assertFalse(r.getBoolean("ok")); assertEquals("vault", r.getString("error")); assertEquals(3, r.getInt("id"))
    }

    @Test fun unknownCommandGivesBadRequest() {
        val r = commands.handle(JSONObject().put("id", 4).put("cmd", "nesmysl"))
        assertFalse(r.getBoolean("ok")); assertEquals("bad_request", r.getString("error"))
    }
}
