package com.claudewatch.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import com.claudewatch.mobile.ui.SettingsScreen
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

class MainActivity : ComponentActivity() {
    private lateinit var settingsStore: SettingsStore
    private val scope = CoroutineScope(Dispatchers.IO)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        settingsStore = SettingsStore(this)

        setContent {
            val serverUrl by settingsStore.serverUrl.collectAsState(initial = "")
            val apiKey by settingsStore.apiKey.collectAsState(initial = "")
            val askKey by settingsStore.askKey.collectAsState(initial = "")
            var registrationStatus by remember { mutableStateOf("") }

            SettingsScreen(
                serverUrl = serverUrl,
                apiKey = apiKey,
                askKey = askKey,
                onSaveServerUrl = { url ->
                    scope.launch { settingsStore.saveServerUrl(url) }
                },
                onSaveApiKey = { key ->
                    scope.launch { settingsStore.saveApiKey(key) }
                },
                onSaveAskKey = { url, key ->
                    scope.launch {
                        settingsStore.saveAskKey(key)
                        // No mandar una URL o una clave vacia: cualquiera de
                        // las dos desactivaria el reloj en silencio.
                        // Sin http(s):// el reloj no puede construir el
                        // cliente: mejor no mandarla.
                        val validUrl = url.startsWith("http://") || url.startsWith("https://")
                        if (validUrl && key.isNotBlank()) {
                            // Envuelto en runCatching: si putDataItem falla
                            // (Play Services no disponible), no debe
                            // cancelar este scope compartido y silenciar
                            // "Register Device" despues.
                            runCatching { DataLayerSender.sendConfig(this@MainActivity, url, key) }
                        }
                    }
                },
                onRegisterDevice = {
                    scope.launch {
                        try {
                            val token = FirebaseMessaging.getInstance().token.await()
                            val url = settingsStore.getServerUrlSync()
                            val key = settingsStore.getApiKeySync()
                            val api = ApiClient.create(url)
                            api.registerDevice(DeviceRegistrationBody(token), key)
                            registrationStatus = "Registered: ${token.take(20)}..."
                        } catch (e: Exception) {
                            registrationStatus = "Error: ${e.message}"
                        }
                    }
                },
                registrationStatus = registrationStatus,
            )
        }
    }
}
