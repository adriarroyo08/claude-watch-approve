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
                event.dataItem.uri.path == "/claude-watch/summary"
            ) {
                val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
                val toolName = dataMap.getString("tool_name") ?: return@forEach
                val summary = dataMap.getString("summary") ?: return@forEach

                Log.d("ClaudeWatch", "Summary received: $toolName - $summary")

                SummaryNotificationManager.showNotification(
                    context = applicationContext,
                    toolName = toolName,
                    summary = summary,
                )
            }
        }
    }
}
