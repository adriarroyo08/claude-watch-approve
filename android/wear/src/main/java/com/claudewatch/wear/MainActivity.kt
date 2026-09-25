package com.claudewatch.wear

import android.content.Intent
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import com.claudewatch.wear.ask.AskActivity
import com.claudewatch.wear.ui.SummaryScreen
import com.claudewatch.wear.ui.WaitingScreen
import com.google.android.gms.wearable.*

class MainActivity : ComponentActivity(), DataClient.OnDataChangedListener {
    private var currentSummary by mutableStateOf<SummaryData?>(null)

    data class SummaryData(val toolName: String, val summary: String)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val summary = currentSummary
            if (summary != null) {
                SummaryScreen(
                    toolName = summary.toolName,
                    summary = summary.summary,
                    onDismiss = { currentSummary = null },
                )
            } else {
                WaitingScreen(onAsk = {
                    startActivity(Intent(this, AskActivity::class.java))
                })
            }
        }
    }

    override fun onResume() {
        super.onResume()
        Wearable.getDataClient(this).addListener(this)
    }

    override fun onPause() {
        super.onPause()
        Wearable.getDataClient(this).removeListener(this)
    }

    override fun onDataChanged(events: DataEventBuffer) {
        events.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED &&
                event.dataItem.uri.path == "/claude-watch/summary"
            ) {
                val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
                currentSummary = SummaryData(
                    toolName = dataMap.getString("tool_name") ?: return@forEach,
                    summary = dataMap.getString("summary") ?: return@forEach,
                )
            }
        }
    }
}
