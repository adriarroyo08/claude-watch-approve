package com.claudewatch.wear

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.net.Uri
import androidx.core.app.NotificationCompat

object ApprovalNotificationManager {
    private const val CHANNEL_ID = "claude_approvals"
    private const val NOTIFICATION_ID_BASE = 1000

    fun showNotification(
        context: Context,
        approvalId: String,
        toolName: String,
        summary: String,
    ) {
        createChannel(context)

        val approveIntent = Intent(context, ApprovalActionReceiver::class.java).apply {
            action = "APPROVE"
            putExtra("approval_id", approvalId)
        }
        val approvePending = PendingIntent.getBroadcast(
            context, approvalId.hashCode(), approveIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val denyIntent = Intent(context, ApprovalActionReceiver::class.java).apply {
            action = "DENY"
            putExtra("approval_id", approvalId)
        }
        val denyPending = PendingIntent.getBroadcast(
            context, approvalId.hashCode() + 1, denyIntent,
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
        val soundUri = Uri.parse("android.resource://${context.packageName}/${R.raw.approval_sound}")
        val audioAttributes = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()

        val channel = NotificationChannel(
            CHANNEL_ID,
            "Claude Approvals",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Claude Code tool execution approval requests"
            setSound(soundUri, audioAttributes)
            vibrationPattern = longArrayOf(0, 200, 100, 200)
            enableVibration(true)
        }

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(channel)
    }
}
