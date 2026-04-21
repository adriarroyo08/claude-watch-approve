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
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.*

@Composable
fun ApprovalScreen(
    toolName: String,
    summary: String,
    onApprove: () -> Unit,
    onDeny: () -> Unit,
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
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }

        item {
            Row(
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier.padding(top = 12.dp),
            ) {
                Button(
                    onClick = onDeny,
                    colors = ButtonDefaults.buttonColors(backgroundColor = Color(0xFFD32F2F)),
                    modifier = Modifier.size(60.dp),
                ) {
                    Text("X", fontSize = 20.sp)
                }
                Button(
                    onClick = onApprove,
                    colors = ButtonDefaults.buttonColors(backgroundColor = Color(0xFF388E3C)),
                    modifier = Modifier.size(60.dp),
                ) {
                    Text("OK", fontSize = 16.sp)
                }
            }
        }
    }
}

@Composable
fun WaitingScreen() {
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
                text = "Waiting for requests...",
                style = MaterialTheme.typography.body2,
                color = Color.Gray,
            )
        }
    }
}
