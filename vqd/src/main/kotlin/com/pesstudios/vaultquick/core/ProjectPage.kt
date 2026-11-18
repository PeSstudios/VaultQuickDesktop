package com.pesstudios.vaultquick.core

/** Stránka, ke které se záznam přiřadí (relativní cesta s .md); úkoly na ni odkazují názvem. */
data class ProjectRef(val path: String) {
    val name: String get() = path.substringAfterLast('/').removeSuffix(".md")
}
