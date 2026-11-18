package com.pesstudios.vaultquick.core

import java.net.URLEncoder

/**
 * Markdown → HTML ve stylu Obsidianu (režim čtení): jednoduché konce řádků zůstávají, `[[odkazy]]`, `#tagy`,
 * callouty. Hotové HTML (bloky kódu) se předává zástupnými znaky [placeholder]. Převzato ze SF Launcheru.
 */
object Markdown {
    private const val MARK = '\u0000'
    val PLACEHOLDER = Regex("\u0000(\\d+)\u0000")

    fun placeholder(n: Int) = "$MARK$n$MARK"

    /** [res] převede místní zdroj obrázku (`kříž.png`) na URL; null = nechat beze změny. */
    fun toHtml(md: String, res: (String) -> String? = { null }): String =
        MdBlocks(res, intArrayOf(0)).render(md.replace("\r\n", "\n").split('\n'))

    /**
     * Celá stránka pro náhled: bez frontmatteru, bloky ``` jako kód, řádek `![[stránka]]` (i `#Nadpis`) jako
     * vložený obsah z [note] (cesta a text stránky, null = nenalezena). Zaškrtávací políčka mají `data-task`
     * s pořadím úkolu – stejným, jaké počítá [toggleTask]; ve vloženém obsahu jsou jen pro čtení.
     */
    fun page(
        text: String,
        res: (String) -> String? = { null },
        note: (String) -> Pair<String, String>? = { null },
    ): String = page(text, res, note, stack = emptyList())

    private fun page(text: String, res: (String) -> String?, note: (String) -> Pair<String, String>?, stack: List<String>): String {
        val parts = mutableListOf<String>()
        val out = StringBuilder()
        val lines = stripFrontmatter(text.replace("\r\n", "\n")).split('\n')
        fun hold(html: String) = out.append(placeholder(parts.size)).append('\n').also { parts += html }
        var i = 0
        while (i < lines.size) {
            val embed = NOTE_EMBED.matchEntire(lines[i].trim())?.takeUnless { IMAGE_FILE.containsMatchIn(it.groupValues[1].trim()) }
            if (embed != null) {
                hold(embedNote(embed.groupValues[1].trim(), embed.groupValues[2].trim(), res, note, stack))
                i++
                continue
            }
            val fence = FENCE.matchEntire(lines[i])
            if (fence == null) { out.append(lines[i]).append('\n'); i++; continue }
            var j = i + 1
            while (j < lines.size && !lines[j].trim().startsWith(fence.groupValues[1])) j++
            hold("<pre><code>${escape(lines.subList(i + 1, minOf(j, lines.size)).joinToString("\n"))}</code></pre>")
            i = j + 1
        }
        val tasks = if (stack.isEmpty()) intArrayOf(0) else null
        val html = MdBlocks(res, tasks).render(out.toString().split('\n'))
        return PLACEHOLDER.replace(html) { parts[it.groupValues[1].toInt()] }
    }

    /** Vložená stránka v rámečku s odkazem; zacyklení a hluboké vnoření jen jako odkaz. */
    private fun embedNote(target: String, label: String, res: (String) -> String?, note: (String) -> Pair<String, String>?, stack: List<String>): String {
        val name = target.substringBefore('#')
        val link = "<a class=\"internal-link embed\" href=\"${escape(noteHref(target))}\">${escape(label.ifEmpty { target.replace("#", " > ") })}</a>"
        val found = note(name)?.takeIf { (path, _) -> path !in stack && stack.size < MAX_EMBED_DEPTH } ?: return "<p>$link</p>"
        val heading = target.substringAfter('#', "").trim()
        val body = if (heading.isEmpty() || heading.startsWith("^")) found.second else section(found.second, heading) ?: return "<p>$link</p>"
        return "<div class=\"embed-note\"><div class=\"embed-title\">$link</div>${page(body, res, note, stack + found.first)}</div>"
    }

    /** Sekce od nadpisu [heading] po další nadpis stejné nebo vyšší úrovně; null = nadpis není. */
    internal fun section(text: String, heading: String): String? {
        val lines = text.replace("\r\n", "\n").split('\n')
        var fence = false
        var start = -1
        var level = 0
        for ((k, line) in lines.withIndex()) {
            if (FENCE.matches(line)) fence = !fence
            if (fence) continue
            val m = Regex("^(#{1,6})\\s+(.*?)\\s*#*\\s*$").matchEntire(line) ?: continue
            val l = m.groupValues[1].length
            if (start < 0) {
                if (m.groupValues[2].equals(heading, ignoreCase = true)) { start = k; level = l }
            } else if (l <= level) return lines.subList(start, k).joinToString("\n")
        }
        return if (start < 0) null else lines.subList(start, lines.size).joinToString("\n")
    }

    private const val MAX_EMBED_DEPTH = 3
    private val NOTE_EMBED = Regex("^!\\[\\[([^\\]|]+)(?:\\|([^\\]]*))?]]$")

    /** Přepne [index]-tý úkol (`- [ ]` ↔ `- [x]`) mimo frontmatter a bloky kódu; null = takový není. */
    fun toggleTask(text: String, index: Int): String? {
        val lines = text.split('\n').toMutableList()
        var start = 0
        if (lines.firstOrNull()?.trimEnd() == "---") {
            val end = (1 until lines.size).firstOrNull { lines[it].trimEnd() == "---" }
            if (end != null) start = end + 1
        }
        var fence: String? = null
        var n = 0
        for (k in start until lines.size) {
            val line = lines[k]
            if (fence != null) { if (line.trim().startsWith(fence)) fence = null; continue }
            FENCE.matchEntire(line)?.let { fence = it.groupValues[1]; continue }
            val m = TASK_LINE.find(line) ?: continue
            if (n++ != index) continue
            val box = m.groups[1]!!.range
            lines[k] = line.replaceRange(box, if (line[box.first] == ' ') "x" else " ")
            return lines.joinToString("\n")
        }
        return null
    }

    private val FENCE = Regex("^\\s*(```+|~~~+).*$")
    /** Úkol jako v [MdBlocks] – i v citaci (`> - [ ]`). */
    private val TASK_LINE = Regex("^(?:\\s*>)*\\s*(?:[-*+]|\\d+[.)])\\s+\\[(.)]")

    fun inline(text: String, res: (String) -> String? = { null }): String = MdInline(res).render(text)

    fun escape(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

    fun noteHref(target: String) = "note:" + URLEncoder.encode(target, "UTF-8").replace("+", "%20")

    fun error(message: String) = "<div class=\"render-error\">${escape(message)}</div>"

    fun stripFrontmatter(text: String): String {
        if (!text.startsWith("---")) return text
        val end = text.indexOf("\n---", 3)
        return if (end < 0) text else text.substring(end + 4).substringAfter('\n', "")
    }
}

private val IMAGE_FILE = Regex("\\.(png|jpe?g|gif|webp|svg|bmp|avif)$", RegexOption.IGNORE_CASE)
private val SCHEME = Regex("^[a-zA-Z][a-zA-Z0-9+.-]*:")
private val IMG_TAG = Regex("<img\\b[^>]*>", RegexOption.IGNORE_CASE)
private val SRC = Regex("(\\ssrc=\")([^\"]*)(\")", RegexOption.IGNORE_CASE)

/** `<img src="místní.png">` → URL z [res]. */
private fun rewriteSrc(tag: String, res: (String) -> String?): String {
    if (!tag.startsWith("<img", ignoreCase = true)) return tag
    return SRC.replace(tag) { m ->
        val src = m.groupValues[2]
        if (SCHEME.containsMatchIn(src)) m.value else m.groupValues[1] + Markdown.escape(res(src) ?: src) + m.groupValues[3]
    }
}

/** [tasks] = počítadlo úkolů sdílené i s vnořenými bloky (citace), kvůli `data-task`; null = políčka jen pro čtení. */
private class MdBlocks(private val res: (String) -> String?, private val tasks: IntArray?) {
    private val out = StringBuilder()

    private class Item(val indent: Int, val ordered: Boolean, val number: Int, val text: String) {
        val more = mutableListOf<String>()
        val children = mutableListOf<Item>()
    }

    fun render(lines: List<String>): String {
        var i = 0
        while (i < lines.size) i = block(lines, i)
        return out.toString()
    }

    private fun inline(text: String) = Markdown.inline(text, res)

    private fun block(lines: List<String>, start: Int): Int {
        val t = lines[start].trim()
        val heading = HEADING.matchEntire(t)
        return when {
            t.isEmpty() -> start + 1
            PLACEHOLDER_LINE.matches(t) -> { out.append(t).append('\n'); start + 1 }
            heading != null -> {
                val level = heading.groupValues[1].length
                out.append("<h$level>").append(inline(heading.groupValues[2])).append("</h$level>\n")
                start + 1
            }
            HR.matches(t) -> { out.append("<hr>\n"); start + 1 }
            t.startsWith(">") -> quote(lines, start)
            LIST_ITEM.matches(lines[start]) -> list(lines, start)
            isTableStart(lines, start) -> table(lines, start)
            HTML_BLOCK.containsMatchIn(t) -> html(lines, start)
            else -> paragraph(lines, start)
        }
    }

    private fun startsBlock(lines: List<String>, i: Int): Boolean {
        val t = lines[i].trim()
        return PLACEHOLDER_LINE.matches(t) || HEADING.matches(t) || HR.matches(t) || t.startsWith(">") ||
            LIST_ITEM.matches(lines[i]) || isTableStart(lines, i) || HTML_BLOCK.containsMatchIn(t)
    }

    private fun paragraph(lines: List<String>, start: Int): Int {
        var i = start
        val parts = mutableListOf<String>()
        while (i < lines.size && lines[i].isNotBlank() && (i == start || !startsBlock(lines, i))) {
            parts += inline(lines[i].trim())
            i++
        }
        out.append("<p>").append(parts.joinToString("<br>\n")).append("</p>\n")
        return i
    }

    private fun quote(lines: List<String>, start: Int): Int {
        var i = start
        val inner = mutableListOf<String>()
        while (i < lines.size && lines[i].trimStart().startsWith(">")) {
            inner += lines[i].trimStart().removePrefix(">").removePrefix(" ")
            i++
        }
        val callout = CALLOUT.matchEntire(inner.first().trim())
        if (callout != null) {
            val type = callout.groupValues[1].lowercase()
            val title = callout.groupValues[3].trim().ifEmpty { type.replaceFirstChar { it.uppercase() } }
            out.append("<div class=\"callout callout-${Markdown.escape(type)}\"><div class=\"callout-title\">").append(inline(title))
                .append("</div>").append(MdBlocks(res, tasks).render(inner.drop(1))).append("</div>\n")
        } else {
            out.append("<blockquote>").append(MdBlocks(res, tasks).render(inner)).append("</blockquote>\n")
        }
        return i
    }

    private fun list(lines: List<String>, start: Int): Int {
        val roots = mutableListOf<Item>()
        val stack = ArrayDeque<Item>()
        var i = start
        while (i < lines.size) {
            val line = lines[i]
            val m = LIST_ITEM.matchEntire(line)
            when {
                m != null -> {
                    val marker = m.groupValues[2]
                    val item = Item(indent(m.groupValues[1]), marker[0].isDigit(), marker.dropLast(1).toIntOrNull() ?: 1, m.groupValues[3])
                    while (stack.isNotEmpty() && stack.last().indent >= item.indent) stack.removeLast()
                    (stack.lastOrNull()?.children ?: roots).add(item)
                    stack.addLast(item)
                }
                line.isBlank() -> if (i + 1 < lines.size && LIST_ITEM.matches(lines[i + 1])) { i++; continue } else break
                line[0].isWhitespace() && stack.isNotEmpty() -> stack.last().more += line.trim()
                else -> break
            }
            i++
        }
        renderItems(roots)
        out.append('\n')
        return i
    }

    private fun indent(ws: String) = ws.sumOf { if (it == '\t') 4 else 1 }

    private fun renderItems(items: List<Item>) {
        var k = 0
        while (k < items.size) {
            val ordered = items[k].ordered
            out.append(
                when {
                    !ordered -> "<ul>"
                    items[k].number != 1 -> "<ol start=\"${items[k].number}\">"
                    else -> "<ol>"
                }
            )
            while (k < items.size && items[k].ordered == ordered) {
                val item = items[k++]
                val task = TASK.matchEntire(item.text)
                if (task != null) {
                    out.append("<li class=\"task-list-item\"><input type=\"checkbox\"").append(if (tasks != null) " data-task=\"${tasks[0]++}\"" else " disabled")
                        .append(if (task.groupValues[1] != " ") " checked" else "").append("> ").append(inline(task.groupValues[2]))
                } else {
                    out.append("<li>").append(inline(item.text))
                }
                item.more.forEach { out.append("<br>").append(inline(it)) }
                if (item.children.isNotEmpty()) renderItems(item.children)
                out.append("</li>")
            }
            out.append(if (ordered) "</ol>" else "</ul>")
        }
    }

    private fun isTableStart(lines: List<String>, i: Int) =
        i + 1 < lines.size && lines[i].contains('|') && lines[i + 1].contains('|') && TABLE_SEP.matches(lines[i + 1].trim())

    private fun table(lines: List<String>, start: Int): Int {
        val header = cells(lines[start])
        val align = cells(lines[start + 1]).map { c ->
            val l = c.startsWith(":")
            val r = c.endsWith(":")
            when { l && r -> "center"; r -> "right"; l -> "left"; else -> null }
        }
        fun style(k: Int) = align.getOrNull(k)?.let { " style=\"text-align:$it\"" } ?: ""
        out.append("<div class=\"table-wrap\"><table><thead><tr>")
        header.forEachIndexed { k, c -> out.append("<th${style(k)}>").append(inline(c)).append("</th>") }
        out.append("</tr></thead><tbody>")
        var i = start + 2
        while (i < lines.size && lines[i].isNotBlank() && lines[i].contains('|')) {
            out.append("<tr>")
            cells(lines[i]).forEachIndexed { k, c -> out.append("<td${style(k)}>").append(inline(c)).append("</td>") }
            out.append("</tr>")
            i++
        }
        out.append("</tbody></table></div>\n")
        return i
    }

    /** Buňky řádku tabulky; `|` uvnitř `[[…]]` a `\|` buňku nedělí. */
    private fun cells(line: String): List<String> {
        var s = line.trim()
        if (s.startsWith("|")) s = s.substring(1)
        if (s.endsWith("|") && !s.endsWith("\\|")) s = s.dropLast(1)
        val result = mutableListOf<String>()
        val cur = StringBuilder()
        var depth = 0
        var k = 0
        while (k < s.length) {
            when {
                s[k] == '\\' && k + 1 < s.length && s[k + 1] == '|' -> { cur.append('|'); k += 2; continue }
                s.startsWith("[[", k) -> { depth++; cur.append("[["); k += 2; continue }
                s.startsWith("]]", k) && depth > 0 -> { depth--; cur.append("]]"); k += 2; continue }
                s[k] == '|' && depth == 0 -> { result += cur.toString().trim(); cur.clear() }
                else -> cur.append(s[k])
            }
            k++
        }
        result += cur.toString().trim()
        return result
    }

    private fun html(lines: List<String>, start: Int): Int {
        var i = start
        while (i < lines.size && lines[i].isNotBlank()) {
            out.append(IMG_TAG.replace(lines[i]) { rewriteSrc(it.value, res) }).append('\n')
            i++
        }
        return i
    }

    private companion object {
        val PLACEHOLDER_LINE = Regex("^\u0000\\d+\u0000$")
        val HEADING = Regex("^(#{1,6})\\s+(.*?)(?:\\s+#+)?\\s*$")
        val HR = Regex("^([-*_])(\\s*\\1){2,}$")
        val LIST_ITEM = Regex("^(\\s*)([-*+]|\\d+[.)])(?:\\s+(.*))?$")
        val TASK = Regex("^\\[(.)]\\s*(.*)$")
        val CALLOUT = Regex("^\\[!([\\w-]+)]([+-]?)\\s*(.*)$")
        val TABLE_SEP = Regex("^\\|?\\s*:?-+:?\\s*(\\|\\s*:?-+:?\\s*)*\\|?$")
        val HTML_BLOCK = Regex(
            "^</?(div|details|summary|table|thead|tbody|tfoot|tr|td|th|p|section|article|aside|header|footer|nav|iframe|" +
                "center|figure|figcaption|h[1-6]|ul|ol|li|blockquote|pre|video|audio|hr|style|script)(\\s|>|/|$)",
            RegexOption.IGNORE_CASE,
        )
    }
}

/** Řádkové formátování. Hotové kusy HTML se schovají do [stash], aby je další úpravy nerozbily. */
private class MdInline(private val res: (String) -> String?) {
    private val stash = mutableListOf<String>()

    private fun keep(html: String): String {
        stash += html
        return "\u0001${stash.size - 1}\u0001"
    }

    private fun url(src: String): String {
        if (SCHEME.containsMatchIn(src)) return src
        val decoded = runCatching { java.net.URLDecoder.decode(src.replace("+", "%2B"), "UTF-8") }.getOrDefault(src)
        return res(decoded) ?: src
    }

    fun render(src: String): String {
        val e = Markdown::escape
        var s = BLOCK_ID.replace(src, "")
        s = CODE.replace(s) { keep("<code>" + e(it.groupValues[2]) + "</code>") }
        s = EMBED.replace(s) { m -> keep(embed(m.groupValues[1].trim(), m.groupValues[2].trim())) }
        s = WIKILINK.replace(s) { m ->
            val target = m.groupValues[1].trim().removeSuffix("\\")
            val label = m.groupValues[2].ifEmpty { target.removeSuffix(".md").replace("#", " > ").removePrefix(" > ") }
            keep("<a class=\"internal-link\" href=\"${e(Markdown.noteHref(target))}\">${e(label)}</a>")
        }
        s = MD_IMAGE.replace(s) { m ->
            val alt = m.groupValues[1]
            val size = SIZE.find(alt)
            val name = if (size != null) alt.substring(0, size.range.first) else alt
            val dims = size?.let { d -> " width=\"${d.groupValues[1]}\"" + d.groupValues[2].let { h -> if (h.isEmpty()) "" else " height=\"$h\"" } }.orEmpty()
            keep("<img src=\"${e(url(m.groupValues[2].trim().removeSurrounding("<", ">")))}\" alt=\"${e(name)}\"$dims>")
        }
        s = MD_LINK.replace(s) { m ->
            val href = m.groupValues[2]
            val external = SCHEME.containsMatchIn(href)
            val target = if (external) href else Markdown.noteHref(runCatching { java.net.URLDecoder.decode(href, "UTF-8") }.getOrDefault(href))
            val cls = if (external) "external-link" else "internal-link"
            keep("<a class=\"$cls\" href=\"${e(target)}\">${MdInline(res).render(m.groupValues[1])}</a>")
        }
        s = HTML_TAG.replace(s) { keep(rewriteSrc(it.value, res)) }
        s = URL.replace(s) { keep("<a class=\"external-link\" href=\"${e(it.value)}\">${e(it.value)}</a>") }
        s = e(s)
        s = BOLD.replace(s) { "<strong>${it.groupValues[2]}</strong>" }
        s = ITALIC_STAR.replace(s) { "<em>${it.groupValues[1]}</em>" }
        s = ITALIC_UNDERSCORE.replace(s) { "<em>${it.groupValues[1]}</em>" }
        s = STRIKE.replace(s) { "<del>${it.groupValues[1]}</del>" }
        s = HIGHLIGHT.replace(s) { "<mark>${it.groupValues[1]}</mark>" }
        s = TAG.replace(s) { "${it.groupValues[1]}<a class=\"tag\" href=\"tag:${it.groupValues[2]}\">#${it.groupValues[2]}</a>" }
        return STASHED.replace(s) { stash[it.groupValues[1].toInt()] }
    }

    /** `![[obrázek.png|48]]` → obrázek z vaultu, `![[stránka]]` → odkaz na ni. */
    private fun embed(target: String, option: String): String {
        val e = Markdown::escape
        if (IMAGE_FILE.containsMatchIn(target)) {
            val src = res(target) ?: return "<span class=\"missing-embed\">${e(target)}</span>"
            val size = SIZE.find("|$option")
            val dims = size?.let { d -> " width=\"${d.groupValues[1]}\"" + d.groupValues[2].let { h -> if (h.isEmpty()) "" else " height=\"$h\"" } }.orEmpty()
            return "<img src=\"${e(src)}\" alt=\"${e(target)}\"$dims>"
        }
        val label = option.ifEmpty { target.removeSuffix(".md").replace("#", " > ").removePrefix(" > ") }
        return "<a class=\"internal-link embed\" href=\"${e(Markdown.noteHref(target))}\">${e(label)}</a>"
    }

    private companion object {
        val EMBED = Regex("!\\[\\[([^\\]|]+)(?:\\|([^\\]]*))?]]")
        val BLOCK_ID = Regex("\\s\\^[A-Za-z0-9-]+\\s*$")
        val CODE = Regex("(`+)(.+?)\\1")
        val WIKILINK = Regex("\\[\\[([^\\]|]+)(?:\\|([^\\]]*))?]]")
        val MD_IMAGE = Regex("!\\[([^\\]]*)]\\(([^)]+)\\)")
        val SIZE = Regex("\\|(\\d+)(?:x(\\d+))?$")
        val MD_LINK = Regex("\\[([^\\]]+)]\\(([^)\\s]+)(?:\\s+\"[^\"]*\")?\\)")
        val HTML_TAG = Regex("</?[a-zA-Z][a-zA-Z0-9-]*(\\s+[^<>]*)?/?>")
        val URL = Regex("https?://[^\\s<>\"'\u0000\u0001]*[^\\s<>\"'.,;:!?)\u0000\u0001]")
        val BOLD = Regex("(\\*\\*|__)(?=\\S)(.+?)(?<=\\S)\\1")
        val ITALIC_STAR = Regex("\\*(?=\\S)(.+?)(?<=\\S)\\*")
        val ITALIC_UNDERSCORE = Regex("(?<![\\p{L}\\p{N}_])_(?=\\S)(.+?)(?<=\\S)_(?![\\p{L}\\p{N}_])")
        val STRIKE = Regex("~~(.+?)~~")
        val HIGHLIGHT = Regex("==(.+?)==")
        val TAG = Regex("(^|[\\s(])#([\\p{L}\\p{N}_/-]*[\\p{L}_/-][\\p{L}\\p{N}_/-]*)")
        val STASHED = Regex("\u0001(\\d+)\u0001")
    }
}
