package com.claudewatch.mobile

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "settings")

class SettingsStore(private val context: Context) {
    companion object {
        val SERVER_URL = stringPreferencesKey("server_url")
        val API_KEY = stringPreferencesKey("api_key")
    }

    val serverUrl: Flow<String> = context.dataStore.data.map { it[SERVER_URL] ?: "" }
    val apiKey: Flow<String> = context.dataStore.data.map { it[API_KEY] ?: "" }

    suspend fun saveServerUrl(url: String) {
        context.dataStore.edit { it[SERVER_URL] = url }
    }

    suspend fun saveApiKey(key: String) {
        context.dataStore.edit { it[API_KEY] = key }
    }

    suspend fun getServerUrlSync(): String {
        var url = ""
        context.dataStore.edit { url = it[SERVER_URL] ?: "" }
        return url
    }

    suspend fun getApiKeySync(): String {
        var key = ""
        context.dataStore.edit { key = it[API_KEY] ?: "" }
        return key
    }
}
