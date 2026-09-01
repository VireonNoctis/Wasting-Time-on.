// src/lib/bandwidth-manager.ts

import type {
  TorrentRecord,
} from "./torrent-types";

export interface GlobalBandwidthLimits {
  download: number;
  upload: number;
}

export class BandwidthManager {
  private globalLimits:
    GlobalBandwidthLimits = {
      download: 0,
      upload: 0,
    };

  setGlobalLimits(
    limits: Partial<GlobalBandwidthLimits>,
  ): void {
    if (
      limits.download !== undefined
    ) {
      this.globalLimits.download =
        Math.max(
          0,
          limits.download,
        );
    }

    if (
      limits.upload !== undefined
    ) {
      this.globalLimits.upload =
        Math.max(
          0,
          limits.upload,
        );
    }
  }

  getGlobalLimits(): GlobalBandwidthLimits {
    return {
      ...this.globalLimits,
    };
  }

  distribute(
    torrents: TorrentRecord[],
  ): Map<string, {
    download: number;
    upload: number;
  }> {
    const result =
      new Map<
        string,
        {
          download: number;
          upload: number;
        }
      >();

    const active =
      torrents.filter(
        (torrent) =>
          torrent.state ===
            "downloading" ||
          torrent.state ===
            "seeding",
      );

    if (
      active.length === 0
    ) {
      return result;
    }

    const downloadPerTorrent =
      this.allocate(
        this.globalLimits.download,
        active.length,
      );

    const uploadPerTorrent =
      this.allocate(
        this.globalLimits.upload,
        active.length,
      );

    for (const torrent of active) {
      const ownDownload =
        torrent.limits.download ??
        0;

      const ownUpload =
        torrent.limits.upload ??
        0;

      result.set(
        torrent.id,
        {
          download:
            this.minimumNonZero(
              downloadPerTorrent,
              ownDownload,
            ),

          upload:
            this.minimumNonZero(
              uploadPerTorrent,
              ownUpload,
            ),
        },
      );
    }

    return result;
  }

  private allocate(
    total: number,
    count: number,
  ): number {
    if (
      total <= 0 ||
      count <= 0
    ) {
      return 0;
    }

    return Math.floor(
      total / count,
    );
  }

  private minimumNonZero(
    global: number,
    local: number,
  ): number {
    if (
      global <= 0 &&
      local <= 0
    ) {
      return 0;
    }

    if (
      global <= 0
    ) {
      return local;
    }

    if (
      local <= 0
    ) {
      return global;
    }

    return Math.min(
      global,
      local,
    );
  }
}
