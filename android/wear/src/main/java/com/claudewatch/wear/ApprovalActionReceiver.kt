package com.claudewatch.wear

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

class ApprovalActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val approvalId = intent.getStringExtra("approval_id") ?: return
        val approved = intent.action == "APPROVE"

        Log.d("ClaudeWatch", "Action: $approvalId -> approved=$approved")

        // Dismiss notification
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.cancel(1000 + approvalId.hashCode())

        // Send response via Data Layer
        CoroutineScope(Dispatchers.IO).launch {
            val request = PutDataMapRequest.create("/claude-approval/response").apply {
                dataMap.putString("approval_id", approvalId)
                dataMap.putBoolean("approved", approved)
                dataMap.putLong("timestamp", System.currentTimeMillis())
            }.asPutDataRequest().setUrgent()

            try {
                Wearable.getDataClient(context).putDataItem(request).await()
            } catch (e: Exception) {
                Log.e("ClaudeWatch", "Failed to send response", e)
            }
        }
    }
}
