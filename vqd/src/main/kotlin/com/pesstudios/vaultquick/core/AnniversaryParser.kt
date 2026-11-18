package com.pesstudios.vaultquick.core

/** Řádky s klíčovým slovem výročí a poli Dataview `[klíč:: hodnota]`. */
object AnniversaryParser {
    private val FIELD = Regex("""\[([^\]:]+)::\s*([^\]]*)]""")

    fun parse(
        noteName: String,
        notePath: String,
        noteText: String,
        s: AnniversarySettings = AnniversarySettings(),
    ): List<RawAnniversary> = noteText.lineSequence()
        .filter { it.contains(s.keyword) }
        .mapNotNull { line ->
            val fields = FIELD.findAll(line).associate { it.groupValues[1].trim() to it.groupValues[2].trim() }
            val date = fields[s.dateField]
            if (date.isNullOrBlank()) return@mapNotNull null
            RawAnniversary(
                noteName = noteName,
                notePath = notePath,
                typ = fields[s.typeField].takeUnless { it.isNullOrBlank() } ?: "výročí",
                datum = date,
                misto = fields[s.placeField].orEmpty(),
                popisek = fields[s.labelField].orEmpty(),
            )
        }
        .toList()
}
