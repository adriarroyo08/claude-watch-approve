package com.claudewatch.wear.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material.*

@Composable
fun SummaryScreen(
    toolName: String,
    summary: String,
    onDismiss: () -> Unit,
) {
    ScalingLazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colors.background),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        item {
            Text(
                text = "Claude",
                style = MaterialTheme.typography.caption1,
                color = MaterialTheme.colors.primary,
            )
        }

        item {
            Text(
                text = toolName,
                style = MaterialTheme.typography.title2,
                color = Color.White,
                textAlign = TextAlign.Center,
            )
        }

        item {
            Text(
                text = summary,
                style = MaterialTheme.typography.body2,
                color = Color.LightGray,
                textAlign = TextAlign.Center,
                maxLines = 5,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }

        item {
            CompactChip(
                onClick = onDismiss,
                label = { Text("OK") },
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }
}

@Composable
fun WaitingScreen(onAsk: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colors.background),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "Claude Watch",
                style = MaterialTheme.typography.title3,
                color = MaterialTheme.colors.primary,
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Waiting for summaries...",
                style = MaterialTheme.typography.body2,
                color = Color.Gray,
            )
            Spacer(modifier = Modifier.height(12.dp))
            Chip(
                onClick = onAsk,
                label = { Text("Preguntar") },
                colors = ChipDefaults.primaryChipColors(),
            )
        }
    }
}
