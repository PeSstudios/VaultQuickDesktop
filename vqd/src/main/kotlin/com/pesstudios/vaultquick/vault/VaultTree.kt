package com.pesstudios.vaultquick.vault

import java.io.File

/** Složky a poznámky vaultu pro výběr v nastavení a v okně výročí (bez skrytých položek). */
object VaultTree {
    fun folders(root: File): List<String> = walk(root).filter { it.second.isDirectory }.map { it.first }.sorted()

    fun markdownFiles(root: File): List<String> =
        walk(root).filter { it.second.isFile && it.first.endsWith(".md") }.map { it.first }.sorted()

    /** Všechny soubory (relativní cesty) – pro dohledání obrázků a odkazů jako v Obsidianu. */
    fun files(root: File): List<String> = walk(root).filter { it.second.isFile }.map { it.first }.sorted()

    /**
     * Cíl odkazu `[[cíl]]` / `![[cíl]]` ze stránky [from]: vedle stránky, pak cesta od kořene, pak název kdekoli.
     * Přednost má `.md` (`[[v1.0]]` je stránka `v1.0.md`).
     */
    fun resolve(files: List<String>, from: String, target: String): String? {
        val name = target.removePrefix("/")
        return if (name.endsWith(".md", ignoreCase = true)) find(files, from, name)
        else find(files, from, "$name.md") ?: find(files, from, name)
    }

    private fun find(files: List<String>, from: String, t: String): String? {
        val dir = from.substringBeforeLast('/', "")
        val near = if (dir.isEmpty()) t else "$dir/$t"
        return files.firstOrNull { it.equals(near, ignoreCase = true) }
            ?: files.firstOrNull { it.equals(t, ignoreCase = true) }
            ?: files.firstOrNull { it.endsWith("/$t", ignoreCase = true) }
            ?: files.firstOrNull { it.substringAfterLast('/').equals(t.substringAfterLast('/'), ignoreCase = true) }
    }

    private fun walk(root: File): List<Pair<String, File>> = buildList {
        fun visit(dir: File, prefix: String) {
            for (child in dir.listFiles().orEmpty()) {
                if (child.name.startsWith(".")) continue
                val path = if (prefix.isEmpty()) child.name else "$prefix/${child.name}"
                add(path to child)
                if (child.isDirectory) visit(child, path)
            }
        }
        visit(root, "")
    }
}
