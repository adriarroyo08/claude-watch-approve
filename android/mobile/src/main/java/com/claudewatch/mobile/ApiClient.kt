package com.claudewatch.mobile

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST

data class DeviceRegistrationBody(val fcm_token: String)
data class RegistrationResult(val status: String)

interface ClaudeWatchApi {
    @POST("register-device")
    suspend fun registerDevice(
        @Body body: DeviceRegistrationBody,
        @Header("X-Api-Key") apiKey: String,
    ): RegistrationResult
}

object ApiClient {
    fun create(baseUrl: String): ClaudeWatchApi {
        return Retrofit.Builder()
            .baseUrl(baseUrl.trimEnd('/') + "/")
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ClaudeWatchApi::class.java)
    }
}
