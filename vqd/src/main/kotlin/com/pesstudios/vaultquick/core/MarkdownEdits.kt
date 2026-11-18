package com.pesstudios.vaultquick.core

/** Text editoru s výběrem [start]..[end] (start ≤ end; stejné = kurzor). */
data class EditorText(val text: String, val start: Int, val end: Int = start)

/** Druh značky na začátku řádku. */
enum class LineMarker { BULLET, TASK, NUMBER, QUOTE }

/** Vkládání md formátování z lišty editoru a pokračování seznamu po Enteru. */
object MarkdownEdits {
    /** Odsazení, značka (odrážka, úkol, číslo, citace) a zbytek řádku. */
    private val MARKER = Regex("^([ \\t]*)([-*+] \\[.] |[-*+] |\\d+[.)] |> ?)?(.*)$")
    private val HEADING = Regex("^(#{1,6}) (.*)$")
    private val NUMBER = Regex("^(\\d+)([.)]) $")

    /**
     * Obalí výběr značkami [open]/[close] (bez výběru je vloží a kurzor dá mezi ně). Už obalený
     * výběr – značky kolem něj nebo na jeho okrajích – naopak odbalí.
     */
    fun wrap(e: EditorText, open: String, close: String = open): EditorText {
        val t = e.text
        val sel = t.substring(e.start, e.end)
        if (e.start >= open.length && t.startsWith(open, e.start - open.length) && t.startsWith(close, e.end)) {
            val text = t.substring(0, e.start - open.length) + sel + t.substring(e.end + close.length)
            return EditorText(text, e.start - open.length, e.end - open.length)
        }
        if (sel.length >= open.length + close.length && sel.startsWith(open) && sel.endsWith(close)) {
            val inner = sel.substring(open.length, sel.length - close.length)
            return EditorText(t.substring(0, e.start) + inner + t.substring(e.end), e.start, e.start + inner.length)
        }
        val text = t.substring(0, e.start) + open + sel + close + t.substring(e.end)
        return EditorText(text, e.start + open.length, e.end + open.length)
    }

    /** Odkaz `[text](adresa)`: s výběrem jde kurzor na adresu, bez něj do popisku. */
    fun link(e: EditorText): EditorText {
        val t = e.text
        val sel = t.substring(e.start, e.end)
        val text = t.substring(0, e.start) + "[" + sel + "]()" + t.substring(e.end)
        val cursor = if (sel.isEmpty()) e.start + 1 else e.start + sel.length + 3
        return EditorText(text, cursor)
    }

    /** Nadpis řádku dokola: žádný → # → ## → ### → žádný. */
    fun cycleHeading(e: EditorText): EditorText = mapLines(e) { _, line ->
        val m = HEADING.matchEntire(line)
        val level = m?.groupValues?.get(1)?.length ?: 0
        val body = m?.groupValues?.get(2) ?: line
        if (level >= 3) body else "#".repeat(level + 1) + " " + body
    }

    /**
     * Nastaví značku [marker] vybraným řádkům; když ji už mají všechny (neprázdné), odebere ji.
     * Jinou značku nahradí, čísla řadí od 1.
     */
    fun toggleMarker(e: EditorText, marker: LineMarker): EditorText {
        val lines = selectedLines(e)
        val all = lines.filter { it.isNotBlank() }.ifEmpty { lines }.all { markerOf(it) == marker }
        var n = 0
        return mapLines(e) { _, line ->
            val m = MARKER.matchEntire(line)!!
            val indent = m.groupValues[1]
            val rest = m.groupValues[3]
            when {
                all -> indent + rest
                line.isBlank() && lines.size > 1 -> line
                else -> indent + prefix(marker, ++n) + rest
            }
        }
    }

    /** Odsadí vybrané řádky tabulátorem. */
    fun indent(e: EditorText): EditorText = mapLines(e) { _, line -> "\t" + line }

    /** Ubere vybraným řádkům jedno odsazení (tabulátor nebo až 4 mezery). */
    fun outdent(e: EditorText): EditorText = mapLines(e) { _, line ->
        when {
            line.startsWith("\t") -> line.substring(1)
            else -> line.substring(line.takeWhile { it == ' ' }.length.coerceAtMost(4))
        }
    }

    /**
     * Po vložení Enteru ([before] → [after]) na řádku se značkou ji zopakuje na novém řádku (úkol
     * nezaškrtnutý, číslo o jedna vyšší). Enter na prázdné položce značku smaže a seznam ukončí.
     * Vrací null, když nejde o takový Enter.
     */
    fun continueList(before: EditorText, after: EditorText): EditorText? {
        val s = before.start
        if (before.start != before.end || after.start != s + 1 || after.end != s + 1) return null
        if (after.text.length != before.text.length + 1 || after.text[s] != '\n') return null
        if (!after.text.startsWith(before.text.substring(0, s)) || !after.text.endsWith(before.text.substring(s))) return null
        val lineStart = before.text.lastIndexOf('\n', s - 1) + 1
        val head = before.text.substring(lineStart, s)
        val m = MARKER.matchEntire(head) ?: return null
        val indent = m.groupValues[1]
        val marker = m.groupValues[2].ifEmpty { return null }
        val lineEnd = before.text.indexOf('\n', s).let { if (it < 0) before.text.length else it }
        if (m.groupValues[3].isBlank() && before.text.substring(s, lineEnd).isBlank()) {
            val text = before.text.substring(0, lineStart) + before.text.substring(s)
            return EditorText(text, lineStart)
        }
        val next = when {
            marker.length > 2 && marker[1] == ' ' && marker[2] == '[' -> marker.substring(0, 2) + "[ ] "
            else -> NUMBER.matchEntire(marker)?.let { "${it.groupValues[1].toInt() + 1}${it.groupValues[2]} " } ?: marker
        }
        val insert = "\n" + indent + next
        val text = before.text.substring(0, s) + insert + before.text.substring(s)
        return EditorText(text, s + insert.length)
    }

    private fun markerOf(line: String): LineMarker? {
        val marker = MARKER.matchEntire(line)!!.groupValues[2]
        return when {
            marker.isEmpty() -> null
            marker.startsWith(">") -> LineMarker.QUOTE
            marker[0].isDigit() -> LineMarker.NUMBER
            marker.length > 2 -> LineMarker.TASK
            else -> LineMarker.BULLET
        }
    }

    private fun prefix(marker: LineMarker, n: Int) = when (marker) {
        LineMarker.BULLET -> "- "
        LineMarker.TASK -> "- [ ] "
        LineMarker.NUMBER -> "$n. "
        LineMarker.QUOTE -> "> "
    }

    /** Začátek prvního a konec posledního vybraného řádku (výběr končící za \n poslední řádek nebere). */
    private fun lineBounds(e: EditorText): Pair<Int, Int> {
        val end = if (e.end > e.start && e.text[e.end - 1] == '\n') e.end - 1 else e.end
        val from = e.text.lastIndexOf('\n', e.start - 1) + 1
        val to = e.text.indexOf('\n', end).let { if (it < 0) e.text.length else it }
        return from to to
    }

    private fun selectedLines(e: EditorText): List<String> {
        val (from, to) = lineBounds(e)
        return e.text.substring(from, to).split("\n")
    }

    /**
     * Přepíše vybrané řádky přes [f]. Výběr se posune o změnu délky před ním: začátek o změnu
     * prvního řádku, konec o změnu všech řádků (vždy ale zůstane v upravených řádcích).
     */
    private fun mapLines(e: EditorText, f: (Int, String) -> String): EditorText {
        val (from, to) = lineBounds(e)
        val old = e.text.substring(from, to).split("\n")
        val new = old.mapIndexed(f)
        val block = new.joinToString("\n")
        val text = e.text.substring(0, from) + block + e.text.substring(to)
        val start = (e.start + new[0].length - old[0].length).coerceIn(from, from + new[0].length)
        val end = if (e.start == e.end) start
            else (e.end + block.length - (to - from)).coerceIn(start, from + block.length + (e.end - to).coerceAtLeast(0))
        return EditorText(text, start, end)
    }
}
