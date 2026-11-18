package com.pesstudios.vaultquick.core

import java.text.Normalizer
import java.util.Locale

private val DIACRITICS = Regex("\\p{Mn}+")

/** Bez diakritiky a malými písmeny – pro porovnávání a hledání ("patek" = "pátek"). */
fun normalize(text: String): String =
    Normalizer.normalize(text, Normalizer.Form.NFD).replace(DIACRITICS, "").lowercase(Locale.ROOT)
