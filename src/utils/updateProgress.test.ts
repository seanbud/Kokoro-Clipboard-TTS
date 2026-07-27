import { describe, expect, it } from "vitest";
import {
  EMPTY_UPDATE_PROGRESS,
  updateDownloadProgress,
} from "./updateProgress";

describe("updater download progress", () => {
  it("calculates bounded percentage from streamed chunks", () => {
    const started = updateDownloadProgress(EMPTY_UPDATE_PROGRESS, {
      event: "Started",
      data: { contentLength: 1_000 },
    });
    const halfway = updateDownloadProgress(started, {
      event: "Progress",
      data: { chunkLength: 505 },
    });
    const finished = updateDownloadProgress(halfway, {
      event: "Finished",
    });

    expect(started.percent).toBe(0);
    expect(halfway).toEqual({
      downloadedBytes: 505,
      totalBytes: 1_000,
      percent: 51,
    });
    expect(finished.percent).toBe(100);
  });

  it("reports byte progress when the server omits content length", () => {
    const started = updateDownloadProgress(EMPTY_UPDATE_PROGRESS, {
      event: "Started",
      data: {},
    });
    const progressed = updateDownloadProgress(started, {
      event: "Progress",
      data: { chunkLength: 256 },
    });

    expect(progressed).toEqual({
      downloadedBytes: 256,
      totalBytes: null,
      percent: null,
    });
  });
});
