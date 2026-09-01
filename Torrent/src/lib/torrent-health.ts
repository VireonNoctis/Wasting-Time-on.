// src/lib/torrent-health.ts

import type {
  TorrentRecord,
} from "./torrent-types";

export interface HealthResult {
  stalled: boolean;
  reason?: string;
}

export function evaluateTorrentHealth(
  torrent: TorrentRecord,
  now = Date.now(),
  stalledAfter = 300_000,
): HealthResult {
  if (
    torrent.state !==
      "downloading"
  ) {
    return {
      stalled: false,
    };
  }

  if (
    torrent.progress >= 1
  ) {
    return {
      stalled: false,
    };
  }

  const lastProgress =
    torrent.lastProgressAt ??
    torrent.startedAt ??
    torrent.addedAt;

  const elapsed =
    now - lastProgress;

  if (
    elapsed >= stalledAfter &&
    torrent.peers <= 0
  ) {
    return {
      stalled: true,
      reason:
        "No peers and no progress",
    };
  }

  if (
    elapsed >= stalledAfter * 2
  ) {
    return {
      stalled: true,
      reason:
        "No measurable progress",
    };
  }

  return {
    stalled: false,
  };
}
