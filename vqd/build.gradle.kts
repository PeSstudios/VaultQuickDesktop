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

// Jádro (core/**, vault/, reminders/) je převzaté z Android aplikace VaultQuick a žije
// v src/main/kotlin – projekt je samostatný. Musí zůstat bez importů android.* / androidx.*.

dependencies {
    implementation("org.json:json:20240303")
    testImplementation("junit:junit:4.13.2")
}
