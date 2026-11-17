package com.pesstudios.vaultquick.vault

import com.pesstudios.vaultquick.core.TaskNotesSettings
import java.io.File

/** Verze pro počítač (bez Androidu): nastavení pluginu TaskNotes. Chybějící soubor = výchozí hodnoty. */
object PluginSettings {
    fun taskNotes(root: File): TaskNotesSettings =
        runCatching { File(root, ".obsidian/plugins/tasknotes/data.json").takeIf { it.isFile }?.readText() }
            .getOrNull()?.let(TaskNotesSettings::parse) ?: TaskNotesSettings()
}
