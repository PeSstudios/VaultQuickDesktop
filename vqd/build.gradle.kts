plugins {
    alias(libs.plugins.kotlin.jvm)
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

// Sdílené zdrojáky aplikace bez Androidu – kompilují se přímo, bez kopie.
// Filtr platí pro všechny srcDir, proto jsou vlastní balíky výslovně povolené.
sourceSets {
    main {
        kotlin {
            srcDir("../../app/src/main/java")
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
    implementation(libs.org.json)
    testImplementation(libs.junit)
}
