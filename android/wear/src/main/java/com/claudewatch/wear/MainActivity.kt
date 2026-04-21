package com.claudewatch.wear

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import com.claudewatch.wear.ui.ApprovalScreen
import com.claudewatch.wear.ui.WaitingScreen
import com.google.android.gms.wearable.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

class MainActivity : ComponentActivity(), DataClient.OnDataChangedListener {
    private var currentApproval by mutableStateOf<ApprovalData?>(null)
    private val scope = CoroutineScope(Dispatchers.IO)

    data class ApprovalData(val id: String, val toolName: String, val summary: String)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val approval = currentApproval
            if (approval != null) {
                ApprovalScreen(
                    toolName = approval.toolName,
                    summary = approval.summary,
                    onApprove = { respond(approval.id, true) },
                    onDeny = { respond(approval.id, false) },
                )
            } else {
                WaitingScreen()
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
                event.dataItem.uri.path == "/claude-approval/request"
            ) {
                val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
                currentApproval = ApprovalData(
                    id = dataMap.getString("approval_id") ?: return@forEach,
                    toolName = dataMap.getString("tool_name") ?: return@forEach,
                    summary = dataMap.getString("summary") ?: return@forEach,
                )
            }
        }
    }

    private fun respond(approvalId: String, approved: Boolean) {
        currentApproval = null
        scope.launch {
            val request = PutDataMapRequest.create("/claude-approval/response").apply {
                dataMap.putString("approval_id", approvalId)
                dataMap.putBoolean("approved", approved)
                dataMap.putLong("timestamp", System.currentTimeMillis())
            }.asPutDataRequest().setUrgent()

            try {
                Wearable.getDataClient(this@MainActivity).putDataItem(request).await()
            } catch (e: Exception) {
                Log.e("ClaudeWatch", "Failed to send response", e)
            }
        }
    }
}
