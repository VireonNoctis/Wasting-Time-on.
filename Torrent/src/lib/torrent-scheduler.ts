// src/lib/torrent-scheduler.ts

import type {
  TorrentPriority,
  TorrentRecord,
} from "./torrent-types";

const WEIGHTS: Record<
  TorrentPriority,
  number
> = {
  low: 1,
  normal: 2,
  high: 3,
  critical: 4,
};

export function compareTorrents(
  a: TorrentRecord,
  b: TorrentRecord,
): number {
  const priorityDifference =
    WEIGHTS[b.priority] -
    WEIGHTS[a.priority];

  if (priorityDifference !== 0) {
    return priorityDifference;
  }

  return a.addedAt - b.addedAt;
}

export function sortQueuedTorrents(
  torrents: TorrentRecord[],
): TorrentRecord[] {
  return [...torrents].sort(
    compareTorrents,
  );
}
