package com.claudewatch.wear.ask

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import retrofit2.HttpException

private const val POLL_MILLIS = 2000L

class AskViewModel(app: Application) : AndroidViewModel(app) {

    private val _state = MutableStateFlow<AskState>(AskState.Composing())
    val state: StateFlow<AskState> = _state

    private var settings: WatchSettings? = null
    private var api: AskApi? = null
    private var pollJob: Job? = null
    private var projects: List<ProjectDto> = emptyList()
    private var selected: ProjectDto? = null
    private var writeMode: Boolean = false

    fun start() {
        viewModelScope.launch {
            var loaded = WatchConfig.load(getApplication())
            if (!loaded.isUsable) {
                loaded = recoverFromDataLayer() ?: loaded
            }
            if (!loaded.isUsable) {
                _state.value = AskState.Failed("Abre la app del movil y guarda la clave del reloj")
                return@launch
            }
            settings = loaded
            api = AskApi.create(loaded.baseUrl)
            loadProjects()
        }
    }

    /**
     * Correccion 1. Si el movil mando la config antes de instalar esta
     * version del reloj, el DataItem ya existe pero onDataChanged no vuelve a
     * saltar, asi que el servicio nunca la guardo. Se lee directamente.
     */
    private suspend fun recoverFromDataLayer(): WatchSettings? = try {
        val items = Wearable.getDataClient(getApplication<Application>())
            .getDataItems(Uri.parse("wear://*/claude-watch/config"))
            .await()
        try {
            items.firstOrNull()?.let { item ->
                val map = DataMapItem.fromDataItem(item).dataMap
                val url = map.getString("base_url").orEmpty()
                val key = map.getString("api_key").orEmpty()
                WatchSettings(url, key).takeIf { it.isUsable }?.also {
                    WatchConfig.save(getApplication(), url, key)
                }
            }
        } finally {
            items.release()
        }
    } catch (e: Exception) {
        if (e is CancellationException) throw e
        null
    }

    /**
     * Correccion 2. El servidor manda el motivo concreto en 'detail' (por
     * ejemplo "El plan caduco sin aprobar"). En un reloj no hay log que leer,
     * asi que se ensena ese motivo antes que un mensaje generico.
     */
    private fun messageFor(e: Exception, fallback: String): String = when (e) {
        is HttpException -> e.serverDetail() ?: when (e.code()) {
            403 -> "Clave del reloj no valida"
            409 -> "Hay una consulta en marcha"
            429 -> "Limite de consultas por hora"
            503 -> "El servidor no tiene clave del reloj"
            else -> "Error ${e.code()}"
        }
        else -> fallback
    }

    private suspend fun loadProjects() {
        val client = api ?: return
        val key = settings?.apiKey ?: return
        try {
            val fetched = client.projects(key).projects
            if (fetched.isEmpty()) {
                _state.value = AskState.Failed("No hay proyectos configurados en el servidor")
                return
            }
            projects = fetched
            selected = selected?.let { prev -> fetched.firstOrNull { it.id == prev.id } }
                ?: fetched.first()
            resumePendingJobOrShowComposing()
        } catch (e: Exception) {
            if (e is CancellationException) throw e
            _state.value = AskState.Failed(messageFor(e, "Sin conexion con el servidor"))
        }
    }

    /**
     * Si quedo un job pendiente de una sesion anterior (corte de red,
     * proceso matado, o la persona salio con un plan esperando aprobacion),
     * se retoma en vez de empezar de cero y perder la respuesta.
     */
    private suspend fun resumePendingJobOrShowComposing() {
        val pending = WatchConfig.loadPendingJob(getApplication())
        if (pending != null) {
            _state.value = AskState.Thinking(pending, seconds = 0)
            poll(pending)
        } else {
            showComposing()
        }
    }

    private fun showComposing(canFollowUp: Boolean = false) {
        _state.value = AskState.Composing(
            projects = projects,
            selected = selected,
            writeMode = writeMode,
            canFollowUp = canFollowUp,
        )
    }

    fun selectProject(project: ProjectDto) {
        selected = project
        showComposing()
    }

    fun toggleWriteMode() {
        writeMode = !writeMode
        showComposing()
    }

    fun send(prompt: String, followUp: Boolean = false) {
        val project = selected ?: return
        val client = api ?: return
        val key = settings?.apiKey ?: return
        viewModelScope.launch {
            try {
                val accepted = client.ask(
                    AskBody(
                        project_id = project.id,
                        prompt = prompt,
                        mode = if (writeMode) "write" else "read",
                        thread = if (followUp) "continue" else "new",
                    ),
                    key,
                )
                // Se guarda antes de sondear: si la red se corta a mitad o
                // Wear OS mata el proceso, al reabrir se retoma este job en
                // vez de perder la respuesta.
                WatchConfig.savePendingJob(getApplication(), accepted.job_id)
                _state.value = AskState.Thinking(accepted.job_id, seconds = 0)
                poll(accepted.job_id)
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                _state.value = AskState.Failed(messageFor(e, "Sin conexion"))
            }
        }
    }

    private fun poll(jobId: String) {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            var seconds = 0
            while (true) {
                delay(POLL_MILLIS)
                seconds += (POLL_MILLIS / 1000).toInt()
                val client = api ?: return@launch
                val key = settings?.apiKey ?: return@launch
                val job = try {
                    client.job(jobId, key)
                } catch (e: Exception) {
                    if (e is CancellationException) throw e
                    // Corte de red pasajero: el job pendiente NO se limpia,
                    // asi que "Reintentar" -> start() lo retoma donde se quedo.
                    _state.value = AskState.Failed(messageFor(e, "Sin conexion"))
                    return@launch
                }
                when (job.status) {
                    "running" -> _state.value = AskState.Thinking(jobId, seconds)
                    "awaiting_approval" -> {
                        _state.value = AskState.AwaitingApproval(jobId, job.plan.orEmpty())
                        // No se limpia el job pendiente: la persona puede
                        // irse y volver dentro de la ventana de 5 minutos
                        // para aprobar.
                        return@launch
                    }
                    "done" -> {
                        _state.value = AskState.Answered(
                            jobId = jobId,
                            short = job.short.orEmpty(),
                            full = job.full.orEmpty(),
                        )
                        // Se limpia DESPUES de fijar Answered: reabrir una
                        // vez todavia ensena la respuesta a traves del
                        // estado en memoria; la siguiente apertura ya
                        // empieza de cero.
                        WatchConfig.clearPendingJob(getApplication())
                        return@launch
                    }
                    "cancelled" -> {
                        WatchConfig.clearPendingJob(getApplication())
                        showComposing()
                        return@launch
                    }
                    else -> {
                        WatchConfig.clearPendingJob(getApplication())
                        _state.value = AskState.Failed(job.error ?: "Error")
                        return@launch
                    }
                }
            }
        }
    }

    fun approve() {
        val current = _state.value as? AskState.AwaitingApproval ?: return
        val client = api ?: return
        val key = settings?.apiKey ?: return
        // Se fija el estado antes de llamar a la red: una segunda pulsacion
        // rapida ya no encuentra AwaitingApproval y no reenvia la aprobacion.
        _state.value = AskState.Thinking(current.jobId, seconds = 0)
        viewModelScope.launch {
            try {
                client.approve(current.jobId, key)
                poll(current.jobId)
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                _state.value = AskState.Failed(messageFor(e, "No se pudo aprobar"))
            }
        }
    }

    /**
     * Correccion 3. El servidor devuelve el estado REAL al cancelar. Si el
     * trabajo ya habia terminado devuelve "done": entonces se ensena la
     * respuesta en vez de tirarla. Con permiso de escritura, los archivos ya
     * estaban tocados, y volver a la pantalla de preguntar lo ocultaria.
     */
    fun cancel() {
        val jobId = when (val current = _state.value) {
            is AskState.Thinking -> current.jobId
            is AskState.AwaitingApproval -> current.jobId
            else -> null
        } ?: return
        pollJob?.cancel()
        val client = api ?: return
        val key = settings?.apiKey ?: return
        // Se abandona el estado que tenia el boton Cancelar antes de llamar
        // a la red: una segunda pulsacion rapida ya no encuentra Thinking ni
        // AwaitingApproval y no reenvia el cancel.
        showComposing()
        viewModelScope.launch {
            val status = try {
                client.cancel(jobId, key).status
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                null
            }
            when (status) {
                "done" -> poll(jobId)
                null -> {
                    // La llamada de cancelar fallo por red: no se sabe si el
                    // trabajo se cancelo de verdad, asi que se deja el job
                    // pendiente para poder retomarlo la proxima vez que se
                    // abra el reloj.
                }
                else -> WatchConfig.clearPendingJob(getApplication())
            }
        }
    }

    fun expand() {
        val current = _state.value as? AskState.Answered ?: return
        _state.value = current.copy(expanded = true)
    }

    fun sendToPhone() {
        val current = _state.value as? AskState.Answered ?: return
        val client = api ?: return
        val key = settings?.apiKey ?: return
        viewModelScope.launch {
            runCatching { client.toPhone(current.jobId, key) }
                .onSuccess { _state.value = current.copy(sentToPhone = true) }
        }
    }

    /** Vuelve a la pantalla de preguntar dejando repreguntar sobre el mismo hilo. */
    fun prepareFollowUp() {
        pollJob?.cancel()
        viewModelScope.launch { WatchConfig.clearPendingJob(getApplication()) }
        showComposing(canFollowUp = true)
    }
}
