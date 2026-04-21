package com.claudewatch.mobile

import android.util.Log
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class DataLayerReceiver : WearableListenerService() {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onDataChanged(events: DataEventBuffer) {
        events.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED &&
                event.dataItem.uri.path == "/claude-approval/response"
            ) {
                val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
                val approvalId = dataMap.getString("approval_id") ?: return@forEach
                val approved = dataMap.getBoolean("approved")

                Log.d("ClaudeWatch", "Watch response: $approvalId -> $approved")

                scope.launch {
                    val settings = SettingsStore(applicationContext)
                    val serverUrl = settings.getServerUrlSync()
                    val apiKey = settings.getApiKeySync()
                    if (serverUrl.isNotBlank() && apiKey.isNotBlank()) {
                        try {
                            val api = ApiClient.create(serverUrl)
                            api.respondToApproval(approvalId, ApprovalResponseBody(approved), apiKey)
                        } catch (e: Exception) {
                            Log.e("ClaudeWatch", "Failed to send response", e)
                        }
                    }
                }
            }
        }
    }
}
