package com.claudewatch.mobile

import android.content.Context
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.tasks.await

object DataLayerSender {
    private const val PATH = "/claude-approval/request"

    suspend fun sendApprovalRequest(
        context: Context,
        approvalId: String,
        toolName: String,
        summary: String,
    ) {
        val request = PutDataMapRequest.create(PATH).apply {
            dataMap.putString("approval_id", approvalId)
            dataMap.putString("tool_name", toolName)
            dataMap.putString("summary", summary)
            dataMap.putLong("timestamp", System.currentTimeMillis())
        }.asPutDataRequest().setUrgent()

        Wearable.getDataClient(context).putDataItem(request).await()
    }
}
