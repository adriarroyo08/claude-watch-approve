package com.claudewatch.wear

import android.util.Log
import com.claudewatch.wear.ask.WatchConfig
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.runBlocking

class DataLayerListenerService : WearableListenerService() {
    override fun onDataChanged(events: DataEventBuffer) {
        events.forEach { event ->
            if (event.type != DataEvent.TYPE_CHANGED) return@forEach

            when (event.dataItem.uri.path) {
                "/claude-watch/summary" -> {
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

                "/claude-watch/config" -> {
                    val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
                    val baseUrl = dataMap.getString("base_url") ?: return@forEach
                    val apiKey = dataMap.getString("watch_key") ?: return@forEach

                    Log.d("ClaudeWatch", "Config received: $baseUrl")

                    // WearableListenerService runs onDataChanged off the main thread,
                    // so a blocking suspend call here is safe.
                    runBlocking {
                        WatchConfig.save(applicationContext, baseUrl, apiKey)
                    }
                }
            }
        }
    }
}
