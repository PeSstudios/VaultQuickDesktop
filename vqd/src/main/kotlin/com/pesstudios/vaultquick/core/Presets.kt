package com.pesstudios.vaultquick.core

enum class Kind { NOTE, TASK }

/** APPEND_SECTION = položka na konec sekce [CapturePreset.projectSection] v souboru (ze zástupce v jeho stránce). */
enum class WriteMode { NEW_FILE, APPEND_END, APPEND_START, APPEND_SECTION }

/** Kam předvolba zapisuje. Cesty jsou relativní k vaultu. */
sealed interface Target {
    data class Folder(val path: String) : Target
    data class Note(val path: String) : Target
    data object DailyNote : Target
}

/** Tlačítko v okně zachycení – vše o uložení je dané předem v nastavení. */
data class CapturePreset(
    /** Stabilní id – klíč zástupce a rozepsaného konceptu. */
    val id: String,
    val label: String,
    val emoji: String,
    val kind: Kind,
    val mode: WriteMode,
    val target: Target,
    val fileNameTemplate: String = FileNameTemplate.DEFAULT,
    val tags: List<String> = emptyList(),
    /** Sekce stránky projektu pro odkaz na nový soubor; v režimu APPEND_SECTION sekce, kam se píše. */
    val projectSection: String = "Poznámky",
)

object Presets {
    /** K projektu (stránce) jde přiřadit úkol, poznámka do nového souboru a zápis do sekce – ne připsání ani výročí. */
    fun projectAssignable(p: CapturePreset): Boolean =
        p.kind == Kind.TASK || (p.kind == Kind.NOTE && (p.mode == WriteMode.NEW_FILE || p.mode == WriteMode.APPEND_SECTION))

    /** Platné kombinace druh / režim / cíl (tabulka ve specu). */
    fun isValid(p: CapturePreset): Boolean {
        if (p.label.isBlank()) return false
        val target = p.target
        return when (p.kind) {
            Kind.NOTE -> when (p.mode) {
                WriteMode.NEW_FILE -> target is Target.Folder
                WriteMode.APPEND_END, WriteMode.APPEND_START ->
                    target is Target.DailyNote || (target is Target.Note && target.path.isNotBlank())
                WriteMode.APPEND_SECTION -> p.projectSection.isNotBlank() &&
                    (target is Target.DailyNote || (target is Target.Note && target.path.isNotBlank()))
            }
            Kind.TASK -> p.mode == WriteMode.NEW_FILE && target is Target.Folder
        }
    }

    /**
     * Jednorázový převod předvolby „💡 nápad“ na „📝 poznámka“ (tři typy: úkol, deník, poznámka).
     * Mění jen pole, která mají ještě původní výchozí hodnotu – vlastní úpravy zůstanou.
     */
    fun renameIdeaToNote(list: List<CapturePreset>): List<CapturePreset> = list.map { p ->
        if (p.id != "idea") p
        else p.copy(
            label = if (p.label == "nápad") "poznámka" else p.label,
            emoji = if (p.emoji == "💡") "📝" else p.emoji,
            tags = if (p.tags == listOf("nápad")) emptyList() else p.tags,
            projectSection = if (p.projectSection == "Nápady") "Poznámky" else p.projectSection,
        )
    }

    /**
     * Jednorázově: poznámka (dosud nový soubor) se píše do sekce „📝 Poznámky“ v souboru stolu
     * a přibude předvolba 💡 nápad do sekce „💡 Nápady“ tamtéž (ze zástupce do jeho stránky).
     */
    fun addDeskSections(list: List<CapturePreset>, labels: Labels = Labels()): List<CapturePreset> {
        val converted = list.map { p ->
            if (p.id == "idea" && p.kind == Kind.NOTE && p.mode == WriteMode.NEW_FILE) notePreset(labels).copy(label = p.label, emoji = p.emoji, tags = p.tags)
            else p
        }
        if (converted.any { it.id == IDEA_ID }) return converted
        val at = converted.indexOfFirst { it.id == "idea" }.let { if (it < 0) converted.size else it + 1 }
        return converted.take(at) + ideaPreset(labels) + converted.drop(at)
    }

    const val IDEA_ID = "napad"

    /** Názvy výchozích předvoleb v jazyce aplikace (dodá Android vrstva). */
    data class Labels(
        val task: String = "úkol",
        val note: String = "poznámka",
        val journal: String = "do deníku",
        val section: String = "Poznámky",
        val fileTemplate: String = FileNameTemplate.DEFAULT,
        val noteFolder: String = "nové",
        val idea: String = "nápad",
        /** Soubor „stolu“ (relativní cesta s .md), kam jdou poznámky a nápady bez stránky. */
        val deskFile: String = "stůl.md",
        val notesSection: String = "📝 Poznámky",
        val ideasSection: String = "💡 Nápady",
    )

    private fun notePreset(labels: Labels) =
        CapturePreset("idea", labels.note, "📝", Kind.NOTE, WriteMode.APPEND_SECTION, Target.Note(labels.deskFile), labels.fileTemplate, projectSection = labels.notesSection)

    private fun ideaPreset(labels: Labels) =
        CapturePreset(IDEA_ID, labels.idea, "💡", Kind.NOTE, WriteMode.APPEND_SECTION, Target.Note(labels.deskFile), labels.fileTemplate, projectSection = labels.ideasSection)

    fun defaults(tasksFolder: String, labels: Labels = Labels()): List<CapturePreset> = listOf(
        CapturePreset("task", labels.task, "✅", Kind.TASK, WriteMode.NEW_FILE, Target.Folder(tasksFolder), labels.fileTemplate, projectSection = labels.section),
        notePreset(labels),
        ideaPreset(labels),
        CapturePreset("journal", labels.journal, "📓", Kind.NOTE, WriteMode.APPEND_END, Target.DailyNote, labels.fileTemplate, projectSection = labels.section),
    )
}
