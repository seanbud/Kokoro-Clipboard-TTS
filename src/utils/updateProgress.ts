import type { DownloadEvent } from "@tauri-apps/plugin-updater";

export type UpdateDownloadProgress = {
  downloadedBytes: number;
  totalBytes: number | null;
  percent: number | null;
};

export const EMPTY_UPDATE_PROGRESS: UpdateDownloadProgress = {
  downloadedBytes: 0,
  totalBytes: null,
  percent: null,
};

export function updateDownloadProgress(
  current: UpdateDownloadProgress,
  event: DownloadEvent,
): UpdateDownloadProgress {
  if (event.event === "Started") {
    const totalBytes = event.data.contentLength ?? null;
    return {
      downloadedBytes: 0,
      totalBytes,
      percent: totalBytes && totalBytes > 0 ? 0 : null,
    };
  }

  if (event.event === "Progress") {
    const downloadedBytes = current.downloadedBytes + event.data.chunkLength;
    return {
      ...current,
      downloadedBytes,
      percent: current.totalBytes && current.totalBytes > 0
        ? Math.min(100, Math.round((downloadedBytes / current.totalBytes) * 100))
        : null,
    };
  }

  return {
    ...current,
    percent: current.totalBytes ? 100 : current.percent,
  };
}
