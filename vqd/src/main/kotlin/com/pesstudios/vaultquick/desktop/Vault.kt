package com.pesstudios.vaultquick.desktop

import com.pesstudios.vaultquick.core.Task
import com.pesstudios.vaultquick.core.TaskNotesSettings
import com.pesstudios.vaultquick.vault.PluginSettings
import com.pesstudios.vaultquick.vault.TaskIndex
import java.io.File

/** Souborový vault na počítači: tenká obálka nad indexem úkolů a nastavením TaskNotes. */
class Vault(val root: File, cacheFile: File) {
    private val index = TaskIndex(root, cacheFile)

    /** Nastavení TaskNotes, při každém čtení znovu ze souboru. */
    val settings: TaskNotesSettings get() = PluginSettings.taskNotes(root)

    fun tasks(): List<Task> = index.scan(settings)

    fun available(): Boolean = root.isDirectory
}
