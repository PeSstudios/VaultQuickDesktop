package com.pesstudios.vaultquick.desktop

import com.pesstudios.vaultquick.core.CapturePreset
import com.pesstudios.vaultquick.core.DailyNote
import com.pesstudios.vaultquick.core.DateChoice
import com.pesstudios.vaultquick.core.Kind
import com.pesstudios.vaultquick.core.NoteWriter
import com.pesstudios.vaultquick.core.Presets
import com.pesstudios.vaultquick.core.ProjectRef
import com.pesstudios.vaultquick.core.Target
import com.pesstudios.vaultquick.core.TaskNotesSettings
import com.pesstudios.vaultquick.core.WriteError
import com.pesstudios.vaultquick.vault.FileVaultStorage
import com.pesstudios.vaultquick.vault.VaultTree
import java.io.File
import java.time.ZonedDateTime

/** Nový úkol stejně jako okno zachycení v telefonu: výchozí předvolba úkolu + `NoteWriter` z jádra. */
object Create {
    /** Výchozí předvolba úkolu (složka úkolů TaskNotes) s případným přepsáním z `config.json`. */
    fun preset(s: TaskNotesSettings, override: TaskPresetOverride?): CapturePreset {
        val base = Presets.defaults(s.tasksFolder).first { it.kind == Kind.TASK }
        if (override == null) return base
        return base.copy(
            target = override.folder?.let { Target.Folder(it) } ?: base.target,
            fileNameTemplate = override.fileNameTemplate ?: base.fileNameTemplate,
            tags = override.tags ?: base.tags,
        )
    }

    /** Stránka projektu podle názvu (bez ohledu na velikost písmen); nenalezená = null → úkol bez projektu. */
    fun projectPage(root: File, name: String?): ProjectRef? {
        val wanted = name?.trim()?.takeIf { it.isNotEmpty() } ?: return null
        return VaultTree.markdownFiles(root)
            .firstOrNull { it.substringAfterLast('/').removeSuffix(".md").equals(wanted, ignoreCase = true) }
            ?.let(::ProjectRef)
    }

    /** Zapíše úkol a vrátí jeho cestu; prázdný text → `empty`. */
    fun task(
        root: File,
        s: TaskNotesSettings,
        override: TaskPresetOverride?,
        text: String,
        choice: DateChoice,
        project: String?,
        now: ZonedDateTime,
    ): String {
        // Denní poznámku předvolba úkolu nepoužívá – stačí výchozí umístění.
        val writer = NoteWriter(FileVaultStorage(root), s, DailyNote.parseLocation(null, null))
        return try {
            writer.save(preset(s, override), text, now, choice, projectPage(root, project))
        } catch (e: WriteError) {
            if (e.reason == WriteError.Reason.EMPTY) throw CommandException("empty", "Prázdný text úkolu")
            throw CommandException("failed", "Úkol nejde zapsat: ${e.reason}")
        }
    }
}
