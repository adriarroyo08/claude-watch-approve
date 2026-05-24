package com.claudewatch.wear

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationCompat

object SummaryNotificationManager {
    private const val CHANNEL_ID = "claude_summary"
    private const val NOTIFICATION_ID_BASE = 1000

    fun showNotification(
        context: Context,
        toolName: String,
        summary: String,
    ) {
        createChannel(context)

        val icon = when (toolName) {
            "Sesion" -> android.R.drawable.ic_menu_info_details
            else -> android.R.drawable.ic_dialog_info
        }

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(icon)
            .setContentTitle("Claude: $toolName")
            .setContentText(summary)
            .setStyle(NotificationCompat.BigTextStyle().bigText(summary))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setVibrate(longArrayOf(0, 150, 100, 150))
            .setAutoCancel(true)
            .build()

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID_BASE + summary.hashCode(), notification)
    }

    private fun createChannel(context: Context) {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Claude Summaries",
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Claude Code session summaries"
            vibrationPattern = longArrayOf(0, 150, 100, 150)
            enableVibration(true)
        }

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(channel)
    }
}
