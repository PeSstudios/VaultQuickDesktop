package com.pesstudios.vaultquick.core

/** Nastavení Připomínkovače. Časy v minutách od půlnoci. */
data class ReminderSettings(
    val enabled: Boolean = false,
    val taskReminders: Boolean = true,
    val morningSummary: Boolean = true,
    val morningMinutes: Int = 7 * 60 + 30,
    val eveningBalance: Boolean = true,
    val eveningMinutes: Int = 21 * 60,
    /** Kolik dní předem upozornit na výročí; 0 = vypnuto. */
    val anniversaryLeadDays: Int = 3,
    /** V neděli připojit k večerní bilanci přehled zpožděných úkolů. */
    val weeklyStale: Boolean = true,
    /** Interval přeplánování (a přepočtu widgetu) v hodinách. */
    val refreshHours: Int = 6,
) {
    companion object {
        val REFRESH_OPTIONS = listOf(1, 2, 3, 6, 12)
    }
}
