package com.pesstudios.vaultquick.core

/**
 * Zpět/Znovu pro editor. Psaní těsně po sobě (do [groupMs]) tvoří jeden krok, takže Zpět neubírá
 * po písmenech.
 */
class EditHistory<T>(private val limit: Int = 200, private val groupMs: Long = 1000) {
    private val undo = ArrayDeque<T>()
    private val redo = ArrayDeque<T>()
    private var lastAt: Long? = null

    val canUndo get() = undo.isNotEmpty()
    val canRedo get() = redo.isNotEmpty()

    /** Zaznamená stav [before] před změnou v čase [at]; [group] = smí se spojit s předchozí změnou. */
    fun record(before: T, at: Long, group: Boolean = true) {
        val last = lastAt
        if (!group || last == null || at - last > groupMs) {
            undo.addLast(before)
            if (undo.size > limit) undo.removeFirst()
        }
        lastAt = if (group) at else null
        redo.clear()
    }

    fun undo(current: T): T? = undo.removeLastOrNull()?.also { redo.addLast(current); lastAt = null }

    fun redo(current: T): T? = redo.removeLastOrNull()?.also { undo.addLast(current); lastAt = null }

    fun clear() { undo.clear(); redo.clear(); lastAt = null }
}
