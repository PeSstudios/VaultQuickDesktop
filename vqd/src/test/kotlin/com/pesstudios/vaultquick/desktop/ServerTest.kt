package com.pesstudios.vaultquick.desktop

import java.io.File
import java.io.StringReader
import java.io.StringWriter
import java.nio.file.Files
import java.time.ZoneId
import java.time.ZonedDateTime
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ServerTest {
    private lateinit var dir: File
    private lateinit var commands: Commands

    @Before fun setUp() {
        dir = Files.createTempDirectory("vqd").toFile()
        val vault = Vault(File(dir, "vault").also { it.mkdirs() }, File(dir, "cache.json"))
        commands = Commands(vault, DesktopConfig()) { ZonedDateTime.of(2026, 11, 17, 9, 0, 0, 0, ZoneId.of("Europe/Prague")) }
    }

    @After fun tearDown() { dir.deleteRecursively() }

    private fun run(input: String): List<String> {
        val out = StringWriter()
        serve(StringReader(input).buffered(), out, commands)
        return out.toString().lines().filter { it.isNotEmpty() }
    }

    @Test fun serveAnswersEachLine() {
        val lines = run("{\"id\":1,\"cmd\":\"meta\"}\n{\"id\":2,\"cmd\":\"meta\"}\n")
        assertEquals(2, lines.size)
        assertEquals(1, JSONObject(lines[0]).getInt("id"))
        assertEquals(2, JSONObject(lines[1]).getInt("id"))
        assertTrue(JSONObject(lines[0]).getBoolean("ok"))
    }

    @Test fun invalidJsonGivesBadRequest() {
        val lines = run("tohle neni json\n{\"id\":5,\"cmd\":\"meta\"}\n")
        assertEquals(2, lines.size)
        val bad = JSONObject(lines[0])
        assertTrue(bad.isNull("id"))
        assertEquals(false, bad.getBoolean("ok"))
        assertEquals("bad_request", bad.getString("error"))
        assertEquals(5, JSONObject(lines[1]).getInt("id"))
    }

    @Test fun brokenConfigFallsBackToDefaults() {
        val f = File(dir, "config.json")
        f.writeText("{ rozbite")
        val broken = loadConfig(f)
        assertNull(broken.vault)
        assertNull(broken.config.taskPreset)
        assertNull(loadConfig(File(dir, "neexistuje.json")).vault)
        f.writeText("""{"vault":"/x/y","taskPreset":{"folder":"T","fileNameTemplate":"{title}","tags":["a"]}}""")
        val ok = loadConfig(f)
        assertEquals("/x/y", ok.vault)
        assertEquals("T", ok.config.taskPreset?.folder)
        assertEquals(listOf("a"), ok.config.taskPreset?.tags)
    }

    @Test fun configVaultExpandsHome() {
        val f = File(dir, "config.json")
        f.writeText("""{"vault":"~/Vault"}""")
        assertEquals("/home/u/Vault", loadConfig(f, "/home/u").vault)
        f.writeText("""{"vault":"~"}""")
        assertEquals("/home/u", loadConfig(f, "/home/u").vault)
        assertEquals("/a/~b", expandHome("/a/~b", "/home/u"))
        assertEquals("~jiny/x", expandHome("~jiny/x", "/home/u"))
    }

    @Test fun cacheFileIsPerVault() {
        val home = dir.path
        val a = File(dir, "a").also { it.mkdirs() }
        val b = File(dir, "b").also { it.mkdirs() }
        val ca = cacheFileFor(home, a)
        assertEquals(File(dir, ".cache/vaultquick-desktop"), ca.parentFile)
        assertTrue(ca.name, ca.name.matches(Regex("tasks-[0-9a-f]{12}\\.idx")))
        assertNotEquals(ca, cacheFileFor(home, b))
        // Stejný vault zadaný jinou cestou → stejný soubor.
        assertEquals(ca, cacheFileFor(home, File(dir, "b/../a")))
    }
}
