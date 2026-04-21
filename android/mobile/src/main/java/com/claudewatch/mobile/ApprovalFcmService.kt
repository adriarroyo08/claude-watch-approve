package com.claudewatch.mobile

import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class ApprovalFcmService : FirebaseMessagingService() {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val approvalId = data["approval_id"] ?: return
        val toolName = data["tool_name"] ?: return
        val summary = data["summary"] ?: return

        Log.d("ClaudeWatch", "FCM received: $toolName - $summary")

        scope.launch {
            DataLayerSender.sendApprovalRequest(
                context = applicationContext,
                approvalId = approvalId,
                toolName = toolName,
                summary = summary,
            )
        }
    }

    override fun onNewToken(token: String) {
        Log.d("ClaudeWatch", "New FCM token: $token")
        scope.launch {
            val settings = SettingsStore(applicationContext)
            val serverUrl = settings.getServerUrlSync()
            val apiKey = settings.getApiKeySync()
            if (serverUrl.isNotBlank() && apiKey.isNotBlank()) {
                try {
                    val api = ApiClient.create(serverUrl)
                    api.registerDevice(DeviceRegistrationBody(token), apiKey)
                } catch (e: Exception) {
                    Log.e("ClaudeWatch", "Failed to register token", e)
                }
            }
        }
    }
}
