package com.claudewatch.wear.ask

sealed interface AskState {
    /** Eligiendo proyecto y modo, esperando a que dictes o teclees. */
    data class Composing(
        val projects: List<ProjectDto> = emptyList(),
        val selected: ProjectDto? = null,
        val writeMode: Boolean = false,
        val canFollowUp: Boolean = false,
    ) : AskState

    data class Thinking(val jobId: String, val seconds: Int) : AskState

    data class AwaitingApproval(val jobId: String, val plan: String) : AskState

    data class Answered(
        val jobId: String,
        val short: String,
        val full: String,
        val expanded: Boolean = false,
        val sentToPhone: Boolean = false,
    ) : AskState

    data class Failed(val message: String) : AskState
}
