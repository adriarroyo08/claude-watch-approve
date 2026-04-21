package com.claudewatch.wear

import androidx.wear.tiles.*
import androidx.wear.tiles.material.*
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.tasks.await as gmsAwait

class ApprovalTileService : TileService() {

    override suspend fun tileRequest(requestParams: RequestBuilders.TileRequest): TileBuilders.Tile {
        val pending = getLatestPendingApproval()

        val timeline = TimelineBuilders.Timeline.Builder()
            .addTimelineEntry(
                TimelineBuilders.TimelineEntry.Builder()
                    .setLayout(
                        LayoutElementBuilders.Layout.Builder()
                            .setRoot(buildLayout(pending))
                            .build()
                    )
                    .build()
            )
            .build()

        return TileBuilders.Tile.Builder()
            .setResourcesVersion("1")
            .setTileTimeline(timeline)
            .setFreshnessIntervalMillis(5000)
            .build()
    }

    override suspend fun resourcesRequest(requestParams: RequestBuilders.ResourcesRequest): ResourceBuilders.Resources {
        return ResourceBuilders.Resources.Builder()
            .setVersion("1")
            .build()
    }

    private fun buildLayout(pending: PendingApproval?): LayoutElementBuilders.LayoutElement {
        if (pending == null) {
            return LayoutElementBuilders.Column.Builder()
                .addContent(
                    LayoutElementBuilders.Text.Builder()
                        .setText("Claude Watch")
                        .setFontStyle(
                            LayoutElementBuilders.FontStyle.Builder()
                                .setSize(DimensionBuilders.sp(14f))
                                .build()
                        )
                        .build()
                )
                .addContent(
                    LayoutElementBuilders.Text.Builder()
                        .setText("No pending requests")
                        .setFontStyle(
                            LayoutElementBuilders.FontStyle.Builder()
                                .setSize(DimensionBuilders.sp(11f))
                                .build()
                        )
                        .build()
                )
                .build()
        }

        return LayoutElementBuilders.Column.Builder()
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText(pending.toolName)
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(16f))
                            .setWeight(LayoutElementBuilders.FONT_WEIGHT_BOLD)
                            .build()
                    )
                    .build()
            )
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText(pending.summary.take(50))
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(11f))
                            .build()
                    )
                    .build()
            )
            .build()
    }

    private suspend fun getLatestPendingApproval(): PendingApproval? {
        return try {
            val dataItems = Wearable.getDataClient(this)
                .getDataItems(android.net.Uri.parse("wear://*/claude-approval/request"))
                .gmsAwait()

            if (dataItems.count > 0) {
                val item = dataItems.get(dataItems.count - 1)
                val dataMap = DataMapItem.fromDataItem(item).dataMap
                PendingApproval(
                    id = dataMap.getString("approval_id") ?: return null,
                    toolName = dataMap.getString("tool_name") ?: return null,
                    summary = dataMap.getString("summary") ?: return null,
                )
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    data class PendingApproval(val id: String, val toolName: String, val summary: String)
}
