plugins {
    kotlin("jvm") version "2.2.10"
    application
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

application {
    mainClass = "com.pesstudios.vaultquick.desktop.MainKt"
    applicationDefaultJvmArgs = listOf("-Xmx96m")
}

// Jádro Android aplikace VaultQuick (vlastnost vaultquickDir v gradle.properties, výchozí
// sourozenecká složka ../VaultQuick). Verze Kotlinu musí odpovídat té v VaultQuick (AGP 9).
val vaultquickApp = rootProject.file(providers.gradleProperty("vaultquickDir").getOrElse("../VaultQuick"))
    .resolve("app/src/main/java")

// Sdílené zdrojáky aplikace bez Androidu – kompilují se přímo, bez kopie.
// POZOR: vqd je kompiluje jako obyčejné JVM (bez Android SDK). Balík core/** (a soubory níže)
// proto musí zůstat bez importů android.* / androidx.* – jinak se vqd nesestaví. Po změně
// v core spusťte `./gradlew :vqd:test` (v ~/VaultQuickDesktop).
// Filtr platí pro všechny srcDir, proto jsou vlastní balíky výslovně povolené.
sourceSets {
    main {
        kotlin {
            srcDir(vaultquickApp)
            srcDir("src/main/kotlin")
            include("com/pesstudios/vaultquick/core/**")
            include("com/pesstudios/vaultquick/vault/FileVaultStorage.kt")
            include("com/pesstudios/vaultquick/vault/TaskIndex.kt")
            include("com/pesstudios/vaultquick/vault/VaultTree.kt")
            include("com/pesstudios/vaultquick/reminders/TaskActions.kt")
            // Vlastní PluginSettings (bez Androidu) – ten z aplikace sem nepatří.
            include("com/pesstudios/vaultquick/vault/PluginSettings.kt")
            exclude { it.file.invariantSeparatorsPath.endsWith("app/src/main/java/com/pesstudios/vaultquick/vault/PluginSettings.kt") }
            include("com/pesstudios/vaultquick/desktop/**")
        }
    }
}

dependencies {
    implementation("org.json:json:20240303")
    testImplementation("junit:junit:4.13.2")
}
