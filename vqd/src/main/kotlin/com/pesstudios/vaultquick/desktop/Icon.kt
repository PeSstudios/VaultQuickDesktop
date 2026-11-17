package com.pesstudios.vaultquick.desktop

import com.pesstudios.vaultquick.core.Frontmatter
import com.pesstudios.vaultquick.core.str
import com.pesstudios.vaultquick.vault.VaultTree
import java.io.File

/** Ikona projektu: vlastnost `ikona` na stránce projektu (zapisuje ji plugin Image Icons v Obsidianu). */
object Icon {
    private val EXTENSIONS = setOf("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp")

    /** Relativní cesta obrázku ikony; neznámý projekt, chybějící vlastnost či soubor nebo ne-obrázek = null. */
    fun of(root: File, project: String?): String? {
        val page = Create.projectPage(root, project)?.path ?: return null
        val file = File(root, page)
        if (!file.isFile) return null
        val value = Frontmatter.parse(file.readText()).str("ikona") ?: return null
        // `[[cíl]]`, `[[cíl|alias]]` i prostá cesta; `#část` a alias se ořežou.
        val target = value.trim().removePrefix("[[").removeSuffix("]]").substringBefore('|').substringBefore('#').trim()
        if (target.isEmpty()) return null
        val found = VaultTree.resolve(VaultTree.files(root), page, target) ?: return null
        return found.takeIf { it.substringAfterLast('.', "").lowercase() in EXTENSIONS }
    }
}
