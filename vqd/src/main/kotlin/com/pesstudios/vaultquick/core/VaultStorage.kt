package com.pesstudios.vaultquick.core

/** Přístup k souborům vaultu; cesty relativní k jeho kořeni. */
interface VaultStorage {
    fun exists(path: String): Boolean
    fun read(path: String): String
    fun write(path: String, content: String)
}
