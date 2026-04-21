package com.claudewatch.mobile.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun SettingsScreen(
    serverUrl: String,
    apiKey: String,
    onSaveServerUrl: (String) -> Unit,
    onSaveApiKey: (String) -> Unit,
    onRegisterDevice: () -> Unit,
    registrationStatus: String,
) {
    var urlField by remember(serverUrl) { mutableStateOf(serverUrl) }
    var keyField by remember(apiKey) { mutableStateOf(apiKey) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Claude Watch Approve", style = MaterialTheme.typography.headlineMedium)

        OutlinedTextField(
            value = urlField,
            onValueChange = { urlField = it },
            label = { Text("Server URL") },
            placeholder = { Text("https://claude-watch.automatito.win") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )

        OutlinedTextField(
            value = keyField,
            onValueChange = { keyField = it },
            label = { Text("API Key") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
        )

        Button(
            onClick = {
                onSaveServerUrl(urlField)
                onSaveApiKey(keyField)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Save Settings")
        }

        Button(
            onClick = onRegisterDevice,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Register Device")
        }

        if (registrationStatus.isNotBlank()) {
            Text(registrationStatus, style = MaterialTheme.typography.bodySmall)
        }
    }
}
