package com.claudewatch.mobile

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat

object MobileApprovalNotificationManager {
    private const val CHANNEL_ID = "claude_approvals"
    private const val NOTIFICATION_ID_BASE = 2000

    fun showNotification(
        context: Context,
        approvalId: String,
        toolName: String,
        summary: String,
    ) {
        createChannel(context)

        val approveIntent = Intent(context, MobileApprovalActionReceiver::class.java).apply {
            action = "APPROVE"
            putExtra("approval_id", approvalId)
        }
        val approvePending = PendingIntent.getBroadcast(
            context, approvalId.hashCode() + 100, approveIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val denyIntent = Intent(context, MobileApprovalActionReceiver::class.java).apply {
            action = "DENY"
            putExtra("approval_id", approvalId)
        }
        val denyPending = PendingIntent.getBroadcast(
            context, approvalId.hashCode() + 101, denyIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val icon = when (toolName) {
            "Bash" -> android.R.drawable.ic_menu_manage
            "Edit" -> android.R.drawable.ic_menu_edit
            "Write" -> android.R.drawable.ic_menu_save
            else -> android.R.drawable.ic_dialog_alert
        }

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(icon)
            .setContentTitle("Claude: $toolName")
            .setContentText(summary)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVibrate(longArrayOf(0, 200, 100, 200))
            .addAction(android.R.drawable.ic_menu_send, "Approve", approvePending)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Deny", denyPending)
            .setAutoCancel(true)
            .build()

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID_BASE + approvalId.hashCode(), notification)
    }

    private fun createChannel(context: Context) {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Claude Approvals",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Claude Code tool execution approval requests"
            vibrationPattern = longArrayOf(0, 200, 100, 200)
            enableVibration(true)
        }

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(channel)
    }
}
