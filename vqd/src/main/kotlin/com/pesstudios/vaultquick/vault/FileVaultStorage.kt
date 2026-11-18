package com.pesstudios.vaultquick.vault

import com.pesstudios.vaultquick.core.VaultStorage
import java.io.File
import java.io.IOException

class FileVaultStorage(val root: File) : VaultStorage {
    override fun exists(path: String) = File(root, path).exists()

    override fun read(path: String) = File(root, path).readText()

    /** Atomický zápis: dočasný soubor + přejmenování, ať Syncthing nevidí napůl zapsaný soubor. */
    override fun write(path: String, content: String) {
        val target = File(root, path)
        val dir = target.parentFile ?: throw IOException("Invalid path: $path")
        if (!dir.isDirectory && !dir.mkdirs()) throw IOException("Cannot create folder ${dir.path}")
        val tmp = File(dir, ".${target.name}.tmp")
        tmp.writeText(content)
        if (!tmp.renameTo(target)) {
            tmp.delete()
            throw IOException("Cannot write ${target.path}")
        }
    }
}
