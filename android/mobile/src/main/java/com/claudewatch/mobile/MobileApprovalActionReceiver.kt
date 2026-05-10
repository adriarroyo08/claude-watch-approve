package com.claudewatch.mobile

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MobileApprovalActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val approvalId = intent.getStringExtra("approval_id") ?: return
        val approved = intent.action == "APPROVE"

        Log.d("ClaudeWatch", "Mobile action: $approvalId -> approved=$approved")

        // Dismiss notification
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.cancel(2000 + approvalId.hashCode())

        // Send response directly to server
        CoroutineScope(Dispatchers.IO).launch {
            val settings = SettingsStore(context)
            val serverUrl = settings.getServerUrlSync()
            val apiKey = settings.getApiKeySync()
            if (serverUrl.isNotBlank() && apiKey.isNotBlank()) {
                try {
                    val api = ApiClient.create(serverUrl)
                    api.respondToApproval(approvalId, ApprovalResponseBody(approved), apiKey)
                    Log.d("ClaudeWatch", "Response sent: $approvalId -> $approved")
                } catch (e: Exception) {
                    Log.e("ClaudeWatch", "Failed to send response", e)
                }
            }
        }
    }
}
