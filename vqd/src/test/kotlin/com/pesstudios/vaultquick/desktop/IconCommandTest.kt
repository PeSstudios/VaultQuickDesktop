package com.pesstudios.vaultquick.desktop

import java.io.File
import java.nio.file.Files
import java.time.ZoneId
import java.time.ZonedDateTime
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class IconCommandTest {
    private lateinit var dir: File
    private lateinit var vault: Vault
    private val now = ZonedDateTime.of(2026, 11, 17, 9, 30, 0, 0, ZoneId.of("Europe/Prague"))

    @Before fun setUp() {
        dir = Files.createTempDirectory("vqd").toFile()
        vault = Vault(File(dir, "vault").also { it.mkdirs() }, File(dir, "cache.json"))
    }

    @After fun tearDown() { dir.deleteRecursively() }

    private fun put(path: String, text: String = "x") {
        val f = File(vault.root, path)
        f.parentFile.mkdirs()
        f.writeText(text)
    }

    private fun page(name: String, frontmatter: String) = put("projekty/$name.md", "---\n$frontmatter\n---\nobsah")

    /** Odpověď příkazu `icon`: cesta, nebo null. */
    private fun icon(project: String): String? {
        val r = Commands(vault, DesktopConfig()) { now }.handle(JSONObject().put("cmd", "icon").put("project", project))
        assertTrue(r.toString(), r.getBoolean("ok"))
        val p = r.getJSONObject("result")
        assertTrue(p.has("path"))
        return if (p.isNull("path")) null else p.getString("path")
    }

    @Test fun iconFromWikilinkPath() {
        put("img/a.png"); page("Alfa", "ikona: \"[[img/a.png]]\"")
        assertEquals("img/a.png", icon("Alfa"))
    }

    @Test fun iconFromBareFileName() {
        put("x/y/g4.png"); page("Alfa", "ikona: \"[[g4.png]]\"")
        assertEquals("x/y/g4.png", icon("Alfa"))
    }

    @Test fun iconWithAlias() {
        put("img/a.png"); page("Alfa", "ikona: \"[[img/a.png|malá]]\"")
        assertEquals("img/a.png", icon("Alfa"))
    }

    @Test fun iconPlainPath() {
        put("img/a.png"); page("Alfa", "ikona: img/a.png")
        assertEquals("img/a.png", icon("Alfa"))
    }

    @Test fun iconUppercaseExtension() {
        put("img/a.PNG"); page("Alfa", "ikona: \"[[img/a.PNG]]\"")
        assertEquals("img/a.PNG", icon("Alfa"))
    }

    @Test fun iconMissingProperty() {
        page("Alfa", "title: Alfa")
        assertEquals(null, icon("Alfa"))
    }

    @Test fun iconMissingFile() {
        page("Alfa", "ikona: \"[[neni.png]]\"")
        assertEquals(null, icon("Alfa"))
    }

    @Test fun iconNotImage() {
        put("projekty/poznámka.md"); page("Alfa", "ikona: \"[[poznámka]]\"")
        assertEquals(null, icon("Alfa"))
    }

    @Test fun iconUnknownProject() {
        assertEquals(null, icon("Nic"))
    }

    @Test fun iconCaseInsensitiveProject() {
        put("img/a.png"); page("Alfa", "ikona: \"[[img/a.png]]\"")
        assertEquals("img/a.png", icon("aLFa"))
    }
}
