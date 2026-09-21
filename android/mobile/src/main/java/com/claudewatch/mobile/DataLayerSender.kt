package com.claudewatch.mobile

import android.content.Context
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.tasks.await

object DataLayerSender {
    private const val PATH = "/claude-watch/summary"
    private const val CONFIG_PATH = "/claude-watch/config"

    suspend fun sendSummary(
        context: Context,
        toolName: String,
        summary: String,
    ) {
        val request = PutDataMapRequest.create(PATH).apply {
            dataMap.putString("tool_name", toolName)
            dataMap.putString("summary", summary)
            dataMap.putLong("timestamp", System.currentTimeMillis())
        }.asPutDataRequest().setUrgent()

        Wearable.getDataClient(context).putDataItem(request).await()
    }

    suspend fun sendConfig(context: Context, baseUrl: String, watchKey: String) {
        val request = PutDataMapRequest.create(CONFIG_PATH).apply {
            dataMap.putString("base_url", baseUrl)
            // Nombre distinto al "api_key" del hook a proposito: son claves
            // distintas, y una futura edicion que las confunda debe fallar
            // al leer, no compilar en silencio con la clave equivocada.
            dataMap.putString("watch_key", watchKey)
            dataMap.putLong("timestamp", System.currentTimeMillis())
        }.asPutDataRequest().setUrgent()

        Wearable.getDataClient(context).putDataItem(request).await()
    }
}
