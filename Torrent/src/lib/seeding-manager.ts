import type {
  TorrentRecord,
} from "./torrent-types";

import type {
  SeedStopReason,
  SeedingPolicy,
  SeedingRecord,
  SeedingRuntime,
} from "./seeding-types";

import {
  evaluateSeeding,
} from "./seeding-policy";

export interface SeedingManagerAdapter {
  getTorrent(
    torrentId: string,
  ): TorrentRecord | undefined;

  startSeeding(
    torrentId: string,
  ): Promise<void>;

  stopSeeding(
    torrentId: string,
  ): Promise<void>;

  getActiveSeedingCount(): number;
}

export interface GlobalSeedingConfig {
  enabled: boolean;

  maxActiveSeeders: number;

  globalUploadLimit: number;

  defaultPolicy: SeedingPolicy;

  evaluationInterval: number;

  maxSeedersPerPeerClass: number;
}

export class SeedingManager {
  private readonly records =
    new Map<string, SeedingRecord>();

  private timer:
    NodeJS.Timeout | null = null;

  private config:
    GlobalSeedingConfig;

  private running = false;

  constructor(
    private readonly adapter:
      SeedingManagerAdapter,
    config: Partial<GlobalSeedingConfig> = {},
  ) {
    this.config = {
      enabled: true,

      maxActiveSeeders: 8,

      globalUploadLimit: 0,

      defaultPolicy: {
        enabled: true,
        mode: "ratio-or-time",

        targetRatio: 2,

        maxSeedTime:
          7 * 24 * 60 * 60 * 1000,

        minSeedTime:
          60 * 60 * 1000,

        idleTimeout:
          6 * 60 * 60 * 1000,

        priority: 0,

        pinned: false,

        forceSeed: false,
      },

      evaluationInterval:
        15_000,

      maxSeedersPerPeerClass:
        100,

      ...config,
    };
  }

  start(): void {
    if (this.running) {
      return;
    }

    this.running = true;

    this.timer =
      setInterval(
        () => {
          void this.evaluateAll();
        },
        this.config
          .evaluationInterval,
      );

    void this.evaluateAll();
  }

  stop(): void {
    this.running = false;

    if (this.timer) {
      clearInterval(
        this.timer,
      );

      this.timer = null;
    }
  }

  setGlobalConfig(
    updates:
      Partial<GlobalSeedingConfig>,
  ): void {
    this.config = {
      ...this.config,
      ...updates,
    };
  }

  getGlobalConfig():
    GlobalSeedingConfig {
    return {
      ...this.config,
    };
  }

  setPolicy(
    torrentId: string,
    policy:
      Partial<SeedingPolicy>,
  ): SeedingRecord {
    const existing =
      this.records.get(
        torrentId,
      );

    const nextPolicy: SeedingPolicy =
      {
        ...(existing?.policy ??
          this.config
            .defaultPolicy),
        ...policy,
      };

    const record: SeedingRecord =
      existing ?? {
        torrentId,

        policy:
          nextPolicy,

        runtime: this.createRuntime(),
      };

    record.policy =
      nextPolicy;

    this.records.set(
      torrentId,
      record,
    );

    return this.clone(record);
  }

  getPolicy(
    torrentId: string,
  ): SeedingRecord {
    const existing =
      this.records.get(
        torrentId,
      );

    if (existing) {
      return this.clone(existing);
    }

    return {
      torrentId,

      policy: {
        ...this.config
          .defaultPolicy,
      },

      runtime:
        this.createRuntime(),
    };
  }

  deletePolicy(
    torrentId: string,
  ): void {
    this.records.delete(
      torrentId,
    );
  }

  async evaluateAll(): Promise<void> {
    if (!this.config.enabled) {
      return;
    }

    const torrents =
      this.getKnownTorrents();

    const candidates =
      torrents
        .filter(
          (torrent) =>
            torrent.progress >= 1 ||
            torrent.state ===
              "seeding",
        )
        .map(
          (torrent) =>
            this.prepareRecord(
              torrent,
            ),
        );

    candidates.sort(
      (a, b) =>
        (b.policy.priority ?? 0) -
        (a.policy.priority ?? 0),
    );

    for (const record of candidates) {
      await this.evaluate(
        record,
        torrents,
      );
    }
  }

  async forceStart(
    torrentId: string,
  ): Promise<void> {
    const torrent =
      this.adapter.getTorrent(
        torrentId,
      );

    if (!torrent) {
      throw new Error(
        `Torrent ${torrentId} not found`,
      );
    }

    const record =
      this.prepareRecord(
        torrent,
      );

    record.policy.forceSeed =
      true;

    record.policy.enabled =
      true;

    await this.adapter.startSeeding(
      torrentId,
    );

    record.runtime.currentlySeeding =
      true;

    record.runtime.startedAt ??=
      Date.now();

    record.runtime.stopReason =
      undefined;
  }

  async forceStop(
    torrentId: string,
  ): Promise<void> {
    const record =
      this.records.get(
        torrentId,
      );

    await this.adapter.stopSeeding(
      torrentId,
    );

    if (record) {
      record.runtime
        .currentlySeeding =
        false;

      record.runtime.stopReason =
        "manual";
    }
  }

  private async evaluate(
    record: SeedingRecord,
    torrents: TorrentRecord[],
  ): Promise<void> {
    const torrent =
      this.adapter.getTorrent(
        record.torrentId,
      );

    if (!torrent) {
      return;
    }

    const now =
      Date.now();

    this.updateRuntime(
      record,
      torrent,
      now,
    );

    const decision =
      evaluateSeeding(
        torrent,
        record.policy,
        record.runtime,
        now,
      );

    if (
      decision.action ===
      "stop"
    ) {
      if (
        record.runtime
          .currentlySeeding
      ) {
        await this.stop(
          record,
          decision.reason!,
        );
      }

      return;
    }

    if (
      decision.action ===
      "wait"
    ) {
      if (
        record.runtime
          .currentlySeeding
      ) {
        await this.stop(
          record,
          decision.reason ===
            "not-scheduled"
            ? "schedule"
            : "disabled",
        );
      }

      return;
    }

    if (
      decision.action ===
        "start" ||
      !record.runtime
        .currentlySeeding
    ) {
      if (
        !this.hasSeedSlot(
          record,
          torrents,
        )
      ) {
        return;
      }

      await this.start(
        record,
      );
    }
  }

  private async start(
    record: SeedingRecord,
  ): Promise<void> {
    await this.adapter.startSeeding(
      record.torrentId,
    );

    const now =
      Date.now();

    record.runtime
      .currentlySeeding =
      true;

    record.runtime.startedAt =
      now;

    record.runtime
      .lastEvaluationAt =
      now;

    record.runtime
      .consecutiveHighPeerChecks =
      0;

    record.runtime.stopReason =
      undefined;
  }

  private async stop(
    record: SeedingRecord,
    reason: SeedStopReason,
  ): Promise<void> {
    await this.adapter.stopSeeding(
      record.torrentId,
    );

    record.runtime
      .currentlySeeding =
      false;

    record.runtime
      .stopReason =
      reason;
  }

  private updateRuntime(
    record: SeedingRecord,
    torrent: TorrentRecord,
    now: number,
  ): void {
    const previous =
      record.runtime
        .lastEvaluationAt;

    if (
      record.runtime
        .currentlySeeding &&
      previous
    ) {
      record.runtime
        .totalSeedTime +=
        now - previous;
    }

    record.runtime
      .lastEvaluationAt =
      now;

    if (
      torrent.peers > 0
    ) {
      record.runtime
        .lastPeerAt =
        now;
    }

    if (
      torrent.uploadSpeed > 0
    ) {
      record.runtime
        .lastUploadAt =
        now;
    }
  }

  private hasSeedSlot(
    record: SeedingRecord,
    torrents: TorrentRecord[],
  ): boolean {
    if (
      record.policy.pinned ||
      record.policy.forceSeed
    ) {
      return true;
    }

    const active =
      this.adapter
        .getActiveSeedingCount();

    if (
      active <
      this.config
        .maxActiveSeeders
    ) {
      return true;
    }

    return false;
  }

  private prepareRecord(
    torrent: TorrentRecord,
  ): SeedingRecord {
    const existing =
      this.records.get(
        torrent.id,
      );

    if (existing) {
      return existing;
    }

    const record: SeedingRecord =
      {
        torrentId: torrent.id,

        policy: {
          ...this.config
            .defaultPolicy,
        },

        runtime:
          this.createRuntime(),
      };

    this.records.set(
      torrent.id,
      record,
    );

    return record;
  }

  private createRuntime():
    SeedingRuntime {
    return {
      totalSeedTime: 0,

      consecutiveHighPeerChecks:
        0,

      currentlySeeding:
        false,
    };
  }

  private getKnownTorrents():
    TorrentRecord[] {
    const output: TorrentRecord[] = [];

    for (
      const id of this.records.keys()
    ) {
      const torrent =
        this.adapter.getTorrent(
          id,
        );

      if (torrent) {
        output.push(torrent);
      }
    }

    return output;
  }

  private clone(
    record: SeedingRecord,
  ): SeedingRecord {
    return {
      torrentId:
        record.torrentId,

      policy: {
        ...record.policy,

        schedule:
          record.policy.schedule
            ? {
                ...record.policy
                  .schedule,
              }
            : undefined,
      },

      runtime: {
        ...record.runtime,
      },
    };
  }
}
