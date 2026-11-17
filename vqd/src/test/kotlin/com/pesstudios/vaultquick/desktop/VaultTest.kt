package com.pesstudios.vaultquick.desktop

import java.io.File
import java.nio.file.Files
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class VaultTest {
    private lateinit var dir: File
    private lateinit var vault: Vault

    @Before fun setUp() {
        dir = Files.createTempDirectory("vqd").toFile()
        vault = Vault(File(dir, "vault").also { it.mkdirs() }, File(dir, "cache.json"))
    }

    @After fun tearDown() { dir.deleteRecursively() }

    private fun note(path: String, title: String): File {
        val f = File(vault.root, path)
        f.parentFile.mkdirs()
        f.writeText("---\ntitle: $title\ntags:\n  - task\nstatus: open\n---\n")
        return f
    }

    @Test fun tasksFoundOutsideTasksFolder() {
        note("domácnost/opravit/x.md", "X")
        note("0 vyřídit/y.md", "Y")
        val paths = vault.tasks().map { it.path }
        assertTrue(paths.toString(), "domácnost/opravit/x.md" in paths && "0 vyřídit/y.md" in paths)
    }

    @Test fun settingsReadFromDataJson() {
        val f = File(vault.root, ".obsidian/plugins/tasknotes/data.json")
        f.parentFile.mkdirs()
        f.writeText(
            """{"tasksFolder":"0 vyřídit","customStatuses":[{"value":"open"},{"value":"in-progress"},{"value":"done","isCompleted":true}]}""",
        )
        assertEquals("0 vyřídit", vault.settings.tasksFolder)
        assertEquals(listOf("open", "in-progress", "done"), vault.settings.statuses)
    }

    @Test fun missingDataJsonGivesDefaults() {
        assertEquals("TaskNotes", vault.settings.tasksFolder)
    }

    @Test fun changedFileIsReread() {
        val f = note("a.md", "Starý")
        assertEquals("Starý", vault.tasks().single().title)
        f.writeText(f.readText().replace("Starý", "Nový"))
        f.setLastModified(f.lastModified() + 2000)
        assertEquals("Nový", vault.tasks().single().title)
    }

    @Test fun deletedFileDisappears() {
        val f = note("a.md", "A")
        assertEquals(1, vault.tasks().size)
        f.delete()
        assertTrue(vault.tasks().isEmpty())
    }

    @Test fun availableOnlyForDirectory() {
        assertTrue(vault.available())
        assertTrue(!Vault(File(dir, "nic"), File(dir, "c")).available())
    }
}
