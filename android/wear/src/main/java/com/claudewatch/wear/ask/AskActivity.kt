package com.claudewatch.wear.ask

import android.app.Activity
import android.app.RemoteInput
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.*
import androidx.core.app.RemoteInput as CoreRemoteInput
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.wear.input.RemoteInputIntentHelper
import com.claudewatch.wear.ask.ui.*

private const val PROMPT_KEY = "prompt"

class AskActivity : ComponentActivity() {

    // A nivel de Activity para que onStart/onStop puedan pausar y retomar
    // el sondeo sin depender de que la composicion siga viva.
    private val model: AskViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val state by model.state.collectAsStateWithLifecycle()
            var pickingProject by remember { mutableStateOf(false) }

            LaunchedEffect(Unit) { model.start() }

            val dictate = rememberLauncherForActivityResult(
                ActivityResultContracts.StartActivityForResult()
            ) { result ->
                if (result.resultCode != Activity.RESULT_OK) return@rememberLauncherForActivityResult
                val data = result.data ?: return@rememberLauncherForActivityResult
                val spoken = CoreRemoteInput.getResultsFromIntent(data)
                    ?.getCharSequence(PROMPT_KEY)?.toString()?.trim()
                // Se lee del estado y no de una variable propia: asi coincide
                // siempre con lo que ensena la pantalla, aunque se cancelara
                // el dictado y despues se cambiara de proyecto o de modo.
                val followUp = (model.state.value as? AskState.Composing)?.canFollowUp == true
                if (!spoken.isNullOrEmpty()) {
                    model.send(spoken, followUp = followUp)
                }
            }

            fun askForText() {
                val remoteInput = RemoteInput.Builder(PROMPT_KEY)
                    .setLabel("Pregunta a Claude")
                    .build()
                val intent = RemoteInputIntentHelper.createActionRemoteInputIntent()
                RemoteInputIntentHelper.putRemoteInputsExtra(intent, listOf(remoteInput))
                dictate.launch(intent)
            }

            when (val current = state) {
                is AskState.Composing ->
                    if (pickingProject) {
                        ProjectPickerScreen(current.projects) { project ->
                            model.selectProject(project)
                            pickingProject = false
                        }
                    } else {
                        ComposingScreen(
                            state = current,
                            onPickProject = { pickingProject = true },
                            onToggleWrite = { model.toggleWriteMode() },
                            onDictate = { askForText() },
                        )
                    }

                is AskState.Thinking ->
                    ThinkingScreen(current.seconds) { model.cancel() }

                is AskState.AwaitingApproval ->
                    PlanScreen(
                        plan = current.plan,
                        onApprove = { model.approve() },
                        onCancel = { model.cancel() },
                    )

                is AskState.Answered ->
                    AnswerScreen(
                        state = current,
                        onExpand = { model.expand() },
                        onToPhone = { model.sendToPhone() },
                        onFollowUp = {
                            model.prepareFollowUp()
                            askForText()
                        },
                    )

                is AskState.Failed ->
                    FailedScreen(current.message) { model.start() }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        // No hace nada en el primer arranque: el estado por defecto es
        // Composing, y solo start() (en LaunchedEffect) decide si hay que
        // retomar un job pendiente.
        model.onForeground()
    }

    override fun onStop() {
        super.onStop()
        model.onBackground()
    }
}
