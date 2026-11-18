package com.pesstudios.vaultquick.vault

import com.pesstudios.vaultquick.core.Task
import com.pesstudios.vaultquick.core.TaskNotes
import com.pesstudios.vaultquick.core.TaskNotesSettings
import java.io.File

/**
 * Index úkolů z celého vaultu. Čte jen frontmatter a pamatuje si výsledek podle data změny
 * souboru (i mezi spuštěními), takže opakovaný průchod jen projde seznam souborů.
 */
class TaskIndex(private val root: File, private val cacheFile: File) {
    private class Entry(val modified: Long, val task: Task?)

    private val entries = HashMap<String, Entry>()
    private var signature: String? = null

    @Synchronized
    fun scan(s: TaskNotesSettings): List<Task> {
        if (signature == null) loadCache(s.signature)
        if (signature != s.signature) {
            entries.clear()
            signature = s.signature
        }
        val seen = HashSet<String>()
        val result = ArrayList<Task>()
        var changed = false
        walk(root, "") { file, path ->
            seen += path
            val modified = file.lastModified()
            val cached = entries[path]
            val entry = if (cached != null && cached.modified == modified) cached else {
                changed = true
                Entry(modified, readTask(file, path, s)).also { entries[path] = it }
            }
            entry.task?.let(result::add)
        }
        if (entries.keys.retainAll(seen)) changed = true
        if (changed) saveCache()
        return result
    }

    private fun walk(dir: File, prefix: String, visit: (File, String) -> Unit) {
        val children = dir.listFiles() ?: return
        for (child in children) {
            if (child.name.startsWith(".")) continue
            val path = if (prefix.isEmpty()) child.name else "$prefix/${child.name}"
            if (child.isDirectory) walk(child, path, visit)
            else if (child.name.endsWith(".md")) visit(child, path)
        }
    }

    private fun readTask(file: File, path: String, s: TaskNotesSettings): Task? = try {
        file.bufferedReader().use { reader ->
            if (reader.readLine()?.trimEnd() != "---") return null
            val head = StringBuilder("---\n")
            for (i in 0 until MAX_FRONTMATTER_LINES) {
                val line = reader.readLine() ?: break
                head.append(line).append('\n')
                if (line.trimEnd() == "---") break
            }
            TaskNotes.parseTask(path, head.toString(), s)
        }
    } catch (_: Exception) {
        null
    }

    // Cache: řádek na soubor, pole oddělená tabulátorem, seznamy znakem US (0x1F).
    private fun saveCache() {
        try {
            val tmp = File(cacheFile.path + ".tmp")
            tmp.bufferedWriter().use { w ->
                w.write(signature.orEmpty()); w.write("\n")
                for ((path, e) in entries) {
                    val t = e.task
                    val fields = mutableListOf(path, e.modified.toString())
                    if (t != null) fields += listOf(
                        t.title, t.status, t.priority, t.scheduled.orEmpty(), t.due.orEmpty(), t.recurrence.orEmpty(),
                        t.completeInstances.joinToString(US), t.skippedInstances.joinToString(US),
                        t.tags.joinToString(US), t.projects.joinToString(US), t.area.orEmpty(),
                        t.reminders.joinToString(US) { r -> r.entries.joinToString(RS) { "${it.key}=${it.value}" } },
                        t.contexts.joinToString(US),
                        t.completedDate?.toString().orEmpty(),
                    )
                    w.write(fields.joinToString("\t") { it.replace('\t', ' ').replace('\n', ' ') })
                    w.write("\n")
                }
            }
            tmp.renameTo(cacheFile)
        } catch (_: Exception) {
        }
    }

    private fun loadCache(expected: String) {
        signature = expected
        if (!cacheFile.exists()) return
        try {
            val lines = cacheFile.readLines()
            if (lines.firstOrNull() != expected) return
            for (line in lines.drop(1)) {
                val f = line.split('\t')
                if (f.size < 2) continue
                val modified = f[1].toLongOrNull() ?: continue
                val task = if (f.size >= 16) Task(
                    path = f[0], title = f[2], status = f[3], priority = f[4],
                    scheduled = f[5].ifEmpty { null }, due = f[6].ifEmpty { null }, recurrence = f[7].ifEmpty { null },
                    completeInstances = f[8].split(US).filter { it.isNotEmpty() },
                    skippedInstances = f[9].split(US).filter { it.isNotEmpty() },
                    tags = f[10].split(US).filter { it.isNotEmpty() },
                    projects = f[11].split(US).filter { it.isNotEmpty() },
                    area = f[12].ifEmpty { null },
                    reminders = f[13].split(US).filter { it.isNotEmpty() }.map { r ->
                        r.split(RS).associate { it.substringBefore('=') to it.substringAfter('=') }
                    },
                    contexts = f[14].split(US).filter { it.isNotEmpty() },
                    completedDate = f[15].ifEmpty { null }?.let { runCatching { java.time.LocalDate.parse(it) }.getOrNull() },
                ) else null
                entries[f[0]] = Entry(modified, task)
            }
        } catch (_: Exception) {
            entries.clear()
        }
    }

    private companion object {
        const val MAX_FRONTMATTER_LINES = 400
        const val US = "\u001F"
        const val RS = "\u001E"
    }
}
