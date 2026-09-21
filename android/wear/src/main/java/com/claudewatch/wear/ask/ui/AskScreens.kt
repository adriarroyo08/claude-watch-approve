package com.claudewatch.wear.ask.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material.*
import com.claudewatch.wear.ask.AskState
import com.claudewatch.wear.ask.ProjectDto

@Composable
fun ComposingScreen(
    state: AskState.Composing,
    onPickProject: () -> Unit,
    onToggleWrite: () -> Unit,
    onDictate: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Chip(
            onClick = onPickProject,
            label = { Text(state.selected?.name ?: "Proyecto") },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        CompactChip(
            onClick = onDictate,
            label = { Text(if (state.canFollowUp) "↻" else "🎤") },
        )
        Spacer(Modifier.height(8.dp))
        ToggleChip(
            checked = state.writeMode,
            onCheckedChange = { onToggleWrite() },
            label = { Text(if (state.writeMode) "Escritura" else "Lectura") },
            toggleControl = {
                Icon(
                    imageVector = ToggleChipDefaults.switchIcon(state.writeMode),
                    contentDescription = null,
                )
            },
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
fun ProjectPickerScreen(
    projects: List<ProjectDto>,
    onPick: (ProjectDto) -> Unit,
) {
    ScalingLazyColumn(modifier = Modifier.fillMaxSize()) {
        items(projects) { project ->
            Chip(
                onClick = { onPick(project) },
                label = { Text(project.name) },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
fun ThinkingScreen(seconds: Int, onCancel: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Spacer(Modifier.height(8.dp))
        Text("pensando", style = MaterialTheme.typography.caption1)
        Text("${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')}")
        Spacer(Modifier.height(8.dp))
        CompactChip(onClick = onCancel, label = { Text("Cancelar") })
    }
}

@Composable
fun PlanScreen(plan: String, onApprove: () -> Unit, onCancel: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Va a hacer esto", style = MaterialTheme.typography.caption1)
        Spacer(Modifier.height(4.dp))
        Text(plan, textAlign = TextAlign.Center, style = MaterialTheme.typography.body2)
        Spacer(Modifier.height(8.dp))
        Chip(
            onClick = onApprove,
            label = { Text("Aprobar") },
            colors = ChipDefaults.primaryChipColors(),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(4.dp))
        Chip(
            onClick = onCancel,
            label = { Text("Cancelar") },
            colors = ChipDefaults.secondaryChipColors(),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
fun AnswerScreen(
    state: AskState.Answered,
    onExpand: () -> Unit,
    onToPhone: () -> Unit,
    onFollowUp: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = if (state.expanded) state.full else state.short,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.body2,
        )
        Spacer(Modifier.height(8.dp))
        if (!state.expanded && state.full.length > state.short.length) {
            CompactChip(onClick = onExpand, label = { Text("Mas") })
            Spacer(Modifier.height(4.dp))
        }
        CompactChip(
            onClick = onToPhone,
            label = { Text(if (state.sentToPhone) "Enviado" else "Al movil") },
        )
        Spacer(Modifier.height(4.dp))
        CompactChip(onClick = onFollowUp, label = { Text("Repreguntar") })
    }
}

@Composable
fun FailedScreen(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message, textAlign = TextAlign.Center, style = MaterialTheme.typography.body2)
        Spacer(Modifier.height(8.dp))
        CompactChip(onClick = onRetry, label = { Text("Reintentar") })
    }
}
