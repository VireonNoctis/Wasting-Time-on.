// src/lib/torrent-history.ts

import type {
  TorrentHistoryPoint,
  TorrentRecord,
} from "./torrent-types";

const MAX_POINTS = 300;

export class TorrentHistory {
  private readonly history =
    new Map<
      string,
      TorrentHistoryPoint[]
    >();

  add(
    torrent: TorrentRecord,
  ): void {
    let points =
      this.history.get(
        torrent.id,
      );

    if (!points) {
      points = [];

      this.history.set(
        torrent.id,
        points,
      );
    }

    points.push({
      timestamp: Date.now(),

      downloadSpeed:
        torrent.downloadSpeed,

      uploadSpeed:
        torrent.uploadSpeed,

      downloaded:
        torrent.downloaded,

      uploaded:
        torrent.uploaded,

      peers:
        torrent.peers,

      progress:
        torrent.progress,
    });

    if (
      points.length >
      MAX_POINTS
    ) {
      points.splice(
        0,
        points.length -
          MAX_POINTS,
      );
    }
  }

  get(
    torrentId: string,
  ): TorrentHistoryPoint[] {
    return [
      ...(this.history.get(
        torrentId,
      ) ?? []),
    ];
  }

  remove(
    torrentId: string,
  ): void {
    this.history.delete(
      torrentId,
    );
  }

  clear(): void {
    this.history.clear();
  }
}
