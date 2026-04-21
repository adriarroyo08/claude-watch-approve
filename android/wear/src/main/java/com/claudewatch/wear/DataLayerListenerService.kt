package com.claudewatch.wear

import android.util.Log
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.WearableListenerService

class DataLayerListenerService : WearableListenerService() {
    override fun onDataChanged(events: DataEventBuffer) {
        events.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED &&
                event.dataItem.uri.path == "/claude-approval/request"
            ) {
                val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
                val approvalId = dataMap.getString("approval_id") ?: return@forEach
                val toolName = dataMap.getString("tool_name") ?: return@forEach
                val summary = dataMap.getString("summary") ?: return@forEach

                Log.d("ClaudeWatch", "Approval request: $toolName - $summary")

                ApprovalNotificationManager.showNotification(
                    context = applicationContext,
                    approvalId = approvalId,
                    toolName = toolName,
                    summary = summary,
                )
            }
        }
    }
}
