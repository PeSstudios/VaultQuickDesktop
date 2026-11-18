package com.pesstudios.vaultquick.core

import java.time.LocalDate

data class Anniversary(
    val noteName: String,
    val notePath: String,
    val typ: String,
    val misto: String,
    val popisek: String,
    val nextOccurrence: LocalDate,
    val kolikate: Int,
    val daysUntil: Long,
    // Name days ("svátky") recur every year regardless of when the note was created, so
    // there's no meaningful "Nth occurrence" to show for them the way there is for a birthday
    // or anniversary.
    val isNameDay: Boolean = false,
)
