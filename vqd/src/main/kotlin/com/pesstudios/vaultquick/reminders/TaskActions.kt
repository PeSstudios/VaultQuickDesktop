package com.pesstudios.vaultquick.reminders

import com.pesstudios.vaultquick.core.TaskEdits
import com.pesstudios.vaultquick.core.TaskNotes
import com.pesstudios.vaultquick.vault.FileVaultStorage
import com.pesstudios.vaultquick.vault.PluginSettings
import java.io.File
import java.time.LocalDate
import java.time.ZonedDateTime

enum class ActionResult { OK, MISSING, FAILED }

/** Úpravy souboru úkolu nad čerstvým obsahem (atomický zápis). */
object TaskActions {
    /** [instance] = výskyt opakovaného úkolu (z agendy); null = podle scheduled. */
    fun complete(root: File, path: String, instance: LocalDate? = null): ActionResult = edit(root, path) { text, task, s ->
        TaskNotes.complete(text, task, s, ZonedDateTime.now(), instance)
    }

    fun postpone(root: File, path: String, date: LocalDate): ActionResult = edit(root, path) { text, task, s ->
        TaskEdits.postpone(text, task, s, date, ZonedDateTime.now())
    }

    fun archive(root: File, path: String): ActionResult = edit(root, path) { text, _, s ->
        TaskEdits.archive(text, s, ZonedDateTime.now())
    }

    private fun edit(
        root: File,
        path: String,
        change: (String, com.pesstudios.vaultquick.core.Task, com.pesstudios.vaultquick.core.TaskNotesSettings) -> String?,
    ): ActionResult {
        val vault = FileVaultStorage(root)
        if (!vault.exists(path)) return ActionResult.MISSING
        return try {
            val s = PluginSettings.taskNotes(root)
            val text = vault.read(path)
            val task = TaskNotes.parseTask(path, text, s) ?: return ActionResult.MISSING
            val updated = change(text, task, s) ?: return ActionResult.FAILED
            vault.write(path, updated)
            ActionResult.OK
        } catch (_: Exception) {
            ActionResult.FAILED
        }
    }
}
