package com.claudewatch.wear.ask

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

private val Context.configStore by preferencesDataStore(name = "claude_watch_config")

/** URL y clave del reloj que el movil empuja por el Data Layer. */
data class WatchSettings(val baseUrl: String, val apiKey: String) {
    val isUsable: Boolean get() = baseUrl.isNotBlank() && apiKey.isNotBlank()
}

object WatchConfig {
    private val URL = stringPreferencesKey("base_url")
    private val KEY = stringPreferencesKey("api_key")

    suspend fun save(context: Context, baseUrl: String, apiKey: String) {
        context.configStore.edit { prefs ->
            prefs[URL] = baseUrl
            prefs[KEY] = apiKey
        }
    }

    suspend fun load(context: Context): WatchSettings {
        val prefs = context.configStore.data.first()
        return WatchSettings(baseUrl = prefs[URL] ?: "", apiKey = prefs[KEY] ?: "")
    }
}
