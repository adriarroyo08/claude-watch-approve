package com.claudewatch.wear.ask

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

data class ProjectDto(val id: String, val name: String)
data class ProjectsResponse(val projects: List<ProjectDto>)

data class AskBody(
    val project_id: String,
    val prompt: String,
    val mode: String,
    val thread: String,
)

data class AskAccepted(val job_id: String, val status: String)

data class JobStatus(
    val status: String,
    val short: String?,
    val full: String?,
    val plan: String?,
    val error: String?,
)

data class SimpleStatus(val status: String)

interface AskApi {
    @GET("projects")
    suspend fun projects(@Header("X-Api-Key") apiKey: String): ProjectsResponse

    @POST("ask")
    suspend fun ask(@Body body: AskBody, @Header("X-Api-Key") apiKey: String): AskAccepted

    @GET("ask/{jobId}")
    suspend fun job(@Path("jobId") jobId: String, @Header("X-Api-Key") apiKey: String): JobStatus

    @POST("ask/{jobId}/approve")
    suspend fun approve(@Path("jobId") jobId: String, @Header("X-Api-Key") apiKey: String): SimpleStatus

    @POST("ask/{jobId}/cancel")
    suspend fun cancel(@Path("jobId") jobId: String, @Header("X-Api-Key") apiKey: String): SimpleStatus

    @POST("ask/{jobId}/to-phone")
    suspend fun toPhone(@Path("jobId") jobId: String, @Header("X-Api-Key") apiKey: String): SimpleStatus

    companion object {
        fun create(baseUrl: String): AskApi = Retrofit.Builder()
            .baseUrl(baseUrl.trimEnd('/') + "/")
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(AskApi::class.java)
    }
}

/** Saca el 'detail' que manda FastAPI en un error, o null si no lo hay. */
fun retrofit2.HttpException.serverDetail(): String? = try {
    response()?.errorBody()?.string()?.let { body ->
        com.google.gson.JsonParser.parseString(body).asJsonObject.get("detail")?.asString
    }
} catch (e: Exception) {
    null
}
