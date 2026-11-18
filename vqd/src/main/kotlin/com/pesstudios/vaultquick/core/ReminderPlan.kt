package com.pesstudios.vaultquick.core

import java.time.LocalDateTime
import java.time.LocalTime

sealed interface Alarm {
    val at: LocalDateTime
    /** Stabilní id pro PendingIntent i notifikaci. */
    val id: Int

    data class TaskReminder(val path: String, val title: String, override val at: LocalDateTime) : Alarm {
        override val id: Int get() = (path + "@" + at).hashCode()
    }

    data class Morning(override val at: LocalDateTime) : Alarm {
        override val id: Int get() = ReminderPlan.MORNING_ID
    }

    data class Evening(override val at: LocalDateTime) : Alarm {
        override val id: Int get() = ReminderPlan.EVENING_ID
    }
}

/** Které budíky mají být nastavené. */
object ReminderPlan {
    const val MORNING_ID = 1001
    const val EVENING_ID = 1002

    fun compute(tasks: List<Task>, s: TaskNotesSettings, r: ReminderSettings, now: LocalDateTime): List<Alarm> {
        if (!r.enabled) return emptyList()
        val alarms = mutableListOf<Alarm>()
        // Ranní budík i jen kvůli předstihu výročí (posílá se v čase ranního souhrnu).
        if (r.morningSummary || r.anniversaryLeadDays > 0) alarms += Alarm.Morning(nextAt(r.morningMinutes, now))
        if (r.eveningBalance) alarms += Alarm.Evening(nextAt(r.eveningMinutes, now))
        if (r.taskReminders) alarms += Reminders.forTasks(tasks, s, now, horizonDays = 7).map { Alarm.TaskReminder(it.path, it.title, it.at) }
        return alarms
    }

    /** Nejbližší výskyt času po [now] – dnes, nebo zítra. */
    private fun nextAt(minutes: Int, now: LocalDateTime): LocalDateTime {
        val today = now.toLocalDate().atTime(LocalTime.of(minutes / 60, minutes % 60))
        return if (today.isAfter(now)) today else today.plusDays(1)
    }
}
