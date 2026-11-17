package com.pesstudios.vaultquick.desktop

import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.io.Writer
import java.time.ZonedDateTime
import org.json.JSONObject

/** Obsah `config.json`: cesta k vaultu (nebo null) a nastavení pro příkazy. */
data class ConfigFile(val vault: String?, val config: DesktopConfig)

/** Načte `config.json`; chybějící nebo rozbitý soubor dá výchozí hodnoty. */
fun loadConfig(file: File): ConfigFile = try {
    if (!file.isFile) {
        ConfigFile(null, DesktopConfig())
    } else {
        val json = JSONObject(file.readText())
        val vault = json.optString("vault", "").takeIf { it.isNotBlank() }
        val preset = json.optJSONObject("taskPreset")?.let { p ->
            TaskPresetOverride(
                folder = p.optString("folder", "").takeIf { it.isNotBlank() },
                fileNameTemplate = p.optString("fileNameTemplate", "").takeIf { it.isNotBlank() },
                tags = p.optJSONArray("tags")?.let { a -> (0 until a.length()).map { a.optString(it) } },
            )
        }
        ConfigFile(vault, DesktopConfig(preset))
    }
} catch (e: Exception) {
    System.err.println("vqd: config.json nelze načíst, používám výchozí: ${e.message}")
    ConfigFile(null, DesktopConfig())
}

/** Čte řádky s požadavky do EOF; na každý zapíše přesně jeden řádek odpovědi a vyprázdní výstup. */
fun serve(input: BufferedReader, output: Writer, commands: Commands) {
    while (true) {
        val line = input.readLine() ?: break
        if (line.isBlank()) continue
        val response = try {
            commands.handle(JSONObject(line))
        } catch (e: Exception) {
            JSONObject().put("id", JSONObject.NULL).put("ok", false)
                .put("error", "bad_request").put("message", "Neplatný JSON: ${e.message}")
        }
        output.write(response.toString())
        output.write("\n")
        output.flush()
    }
}

fun main(args: Array<String>) {
    val home = System.getProperty("user.home")
    val cfg = loadConfig(File(home, ".config/vaultquick-desktop/config.json"))
    val argVault = args.indexOf("--vault").takeIf { it >= 0 }?.let { args.getOrNull(it + 1) }
    val root = File(argVault ?: cfg.vault ?: "$home/MujVault")
    val cache = File(home, ".cache/vaultquick-desktop/tasks.idx")
    cache.parentFile.mkdirs()
    val commands = Commands(Vault(root, cache), cfg.config) { ZonedDateTime.now() }
    val input = BufferedReader(InputStreamReader(System.`in`, Charsets.UTF_8))
    val output = System.out.writer(Charsets.UTF_8)
    serve(input, output, commands)
}
