package com.pesstudios.vaultquick.core

/**
 * Minimální YAML frontmatter: `klíč: hodnota`, seznamy `klíč:` + `  - položka` a `[a, b]`.
 * Úpravy mění jen dotčené řádky, zbytek souboru zůstává beze změny.
 */
object Frontmatter {
    private val KEY = Regex("^([^\\s#:-][^:]*?):(?:\\s+(.*))?$")
    private val LIST_ITEM = Regex("^\\s*-(\\s+.*)?$")

    /** Rozsah řádků uvnitř `---` … `---`, nebo null, když soubor frontmatter nemá. */
    private fun block(lines: List<String>): IntRange? {
        if (lines.firstOrNull()?.trimEnd() != "---") return null
        val end = (1 until lines.size).firstOrNull { lines[it].trimEnd() == "---" } ?: return null
        return 1 until end
    }

    private fun keyOf(line: String): String? = KEY.matchEntire(line)?.groupValues?.get(1)?.trim()

    /** Hodnota je String nebo List<String>. Prázdná hodnota (`klíč:`) = prázdný seznam. */
    fun parse(text: String): Map<String, Any> {
        val lines = text.lines()
        val range = block(lines) ?: return emptyMap()
        val map = LinkedHashMap<String, Any>()
        var list: MutableList<String>? = null
        for (i in range) {
            val line = lines[i]
            if (list != null && LIST_ITEM.matches(line)) {
                list += unquote(line.trim().removePrefix("-").trim())
                continue
            }
            list = null
            val m = KEY.matchEntire(line) ?: continue
            val key = m.groupValues[1].trim()
            val value = m.groupValues[2].trim()
            map[key] = when {
                value.isEmpty() -> mutableListOf<String>().also { list = it }
                value.startsWith("[") && value.endsWith("]") ->
                    value.substring(1, value.length - 1).split(',').map { unquote(it.trim()) }.filter { it.isNotEmpty() }
                else -> unquote(value)
            }
        }
        return map
    }

    /**
     * Seznam objektů (např. `reminders:` v TaskNotes):
     * ```
     * reminders:
     *   - id: rem_1
     *     type: relative
     * ```
     */
    fun objects(text: String, key: String): List<Map<String, String>> {
        val lines = text.lines()
        val range = block(lines) ?: return emptyList()
        val start = range.firstOrNull { keyOf(lines[it]) == key } ?: return emptyList()
        val result = mutableListOf<MutableMap<String, String>>()
        for (i in start + 1..range.last) {
            val line = lines[i]
            if (line.isNotEmpty() && !line[0].isWhitespace()) break
            val trimmed = line.trim()
            val entry = when {
                trimmed.startsWith("- ") -> mutableMapOf<String, String>().also { result += it }.let { it to trimmed.substring(2) }
                result.isNotEmpty() -> result.last() to trimmed
                else -> continue
            }
            val sep = entry.second.indexOf(':')
            if (sep > 0) entry.first[entry.second.substring(0, sep).trim()] = unquote(entry.second.substring(sep + 1).trim())
        }
        return result
    }

    fun setValue(text: String, key: String, value: String): String {
        val lines = text.lines().toMutableList()
        val range = block(lines) ?: return text
        val idx = range.firstOrNull { keyOf(lines[it]) == key }
        if (idx == null) {
            lines.add(range.last + 1, "$key: $value")
        } else {
            lines[idx] = "$key: $value"
            while (idx + 1 < lines.size && LIST_ITEM.matches(lines[idx + 1])) lines.removeAt(idx + 1)
        }
        return lines.joinToString("\n")
    }

    fun addListItem(text: String, key: String, item: String): String {
        val lines = text.lines().toMutableList()
        val range = block(lines) ?: return text
        val idx = range.firstOrNull { keyOf(lines[it]) == key }
        if (idx == null) {
            lines.addAll(range.last + 1, listOf("$key:", "  - $item"))
            return lines.joinToString("\n")
        }
        // Inline hodnotu ([] / [a, b] / skalár) převést na blokový seznam.
        val inline = KEY.matchEntire(lines[idx])!!.groupValues[2].trim()
        if (inline.isNotEmpty()) {
            val existing = if (inline.startsWith("[") && inline.endsWith("]"))
                inline.substring(1, inline.length - 1).split(',').map { it.trim() }.filter { it.isNotEmpty() }
            else listOf(inline)
            lines[idx] = "$key:"
            lines.addAll(idx + 1, existing.map { "  - $it" })
        }
        var end = idx + 1
        while (end < lines.size && LIST_ITEM.matches(lines[end])) end++
        lines.add(end, "  - $item")
        return lines.joinToString("\n")
    }

    /** Smaže klíč ve frontmatteru včetně navazujících položek seznamu. */
    fun removeKey(text: String, key: String): String {
        val lines = text.lines().toMutableList()
        val range = block(lines) ?: return text
        val idx = range.firstOrNull { keyOf(lines[it]) == key } ?: return text
        var end = idx + 1
        while (end < lines.size && LIST_ITEM.matches(lines[end])) end++
        repeat(end - idx) { lines.removeAt(idx) }
        return lines.joinToString("\n")
    }

    /** Odebere položky seznamu, pro které [remove] vrátí true (blokový i inline seznam, skalár jako jedna položka). */
    fun removeListItems(text: String, key: String, remove: (String) -> Boolean): String {
        val lines = text.lines().toMutableList()
        val range = block(lines) ?: return text
        val idx = range.firstOrNull { keyOf(lines[it]) == key } ?: return text
        val inline = KEY.matchEntire(lines[idx])!!.groupValues[2].trim()
        // Skalár (`contexts: kaufland`) = seznam s jednou položkou; po odebrání zbyde prázdný `klíč:`.
        if (inline.isNotEmpty() && !(inline.startsWith("[") && inline.endsWith("]"))) {
            if (remove(unquote(inline))) lines[idx] = "$key:"
            return lines.joinToString("\n")
        }
        if (inline.startsWith("[") && inline.endsWith("]")) {
            val kept = inline.substring(1, inline.length - 1).split(',').map { it.trim() }
                .filter { it.isNotEmpty() && !remove(unquote(it)) }
            lines[idx] = "$key: [" + kept.joinToString(", ") + "]"
            return lines.joinToString("\n")
        }
        var i = idx + 1
        while (i < lines.size && LIST_ITEM.matches(lines[i])) {
            if (remove(unquote(lines[i].trim().removePrefix("-").trim()))) lines.removeAt(i) else i++
        }
        return lines.joinToString("\n")
    }

    private fun unquote(value: String): String = when {
        value.length >= 2 && value.startsWith("\"") && value.endsWith("\"") ->
            value.substring(1, value.length - 1).replace("\\\"", "\"").replace("\\\\", "\\")
        value.length >= 2 && value.startsWith("'") && value.endsWith("'") ->
            value.substring(1, value.length - 1).replace("''", "'")
        else -> value
    }
}

fun Map<String, Any>.str(key: String): String? = (this[key] as? String)?.takeIf { it.isNotBlank() }

fun Map<String, Any>.list(key: String): List<String> = when (val v = this[key]) {
    is List<*> -> v.filterIsInstance<String>()
    is String -> listOf(v)
    else -> emptyList()
}
