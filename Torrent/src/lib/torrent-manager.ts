// src/lib/torrent-manager.ts

import {
  EventEmitter,
} from "node:events";

import path from "node:path";
import fs from "node:fs/promises";

import WebTorrent from "webtorrent";

import {
  torrentDatabase,
} from "./database";

import {
  sortQueuedTorrents,
} from "./torrent-scheduler";

import {
  evaluateTorrentHealth,
} from "./torrent-health";

import {
  retryDelay,
} from "./torrent-retry";

import {
  torrentConfig,
} from "./torrent-config";

import {
  SeedingManager,
} from "./seeding-manager";

import {
  TorrentSeedingAdapter,
} from "./torrent-seeding-adapter";

import type {
  TorrentRecord,
  TorrentState,
  TorrentPriority,
} from "./torrent-types";

import type {
  SeedingPolicy,
  SeedingRecord,
  SeedingRuntime,
} from "./seeding-types";

/* -------------------------------------------------------------------------- */
/* Types                                                                      */
/* -------------------------------------------------------------------------- */

export interface AddTorrentOptions {
  path?: string;

  priority?:
    TorrentPriority;

  startImmediately?:
    boolean;

  seedingPolicy?:
    Partial<SeedingPolicy>;

  downloadLimit?:
    number;

  uploadLimit?:
    number;
}

export interface TorrentManagerEvents {
  update:
    TorrentRecord;

  metadata:
    TorrentRecord;

  added:
    TorrentRecord;

  completed:
    TorrentRecord;

  seeding:
    TorrentRecord;

  stalled:
    TorrentRecord;

  error:
    TorrentRecord;

  removed:
    {
      id: string;
    };
}

/* -------------------------------------------------------------------------- */
/* Manager                                                                    */
/* -------------------------------------------------------------------------- */

export class TorrentManager
  extends EventEmitter {
  private client:
    WebTorrent.Instance | null =
    null;

  private initialized =
    false;

  private initializing:
    Promise<void> | null =
    null;

  private readonly records =
    new Map<
      string,
      TorrentRecord
    >();

  private readonly torrents =
    new Map<
      string,
      WebTorrent.Torrent
    >();

  private readonly seedingManager:
    SeedingManager;

  private healthTimer:
    NodeJS.Timeout | null =
    null;

  private statisticsTimer:
    NodeJS.Timeout | null =
    null;

  private running =
    false;

  private statsWriting =
    false;

  constructor() {
    super();

    /*
     * The adapter keeps the seeding subsystem
     * independent of WebTorrent implementation details.
     */
    this.seedingManager =
      new SeedingManager(
        new TorrentSeedingAdapter(
          {
            get:
              (id) =>
                this.records.get(
                  id,
                ),

            startTorrent:
              (id) =>
                this.resume(
                  id,
                ),

            stopTorrent:
              (id) =>
                this.pause(
                  id,
                ),

            list:
              () =>
                this.list(),
          },
        ),
      );
  }

  /* ------------------------------------------------------------------------ */
  /* Lifecycle                                                                */
  /* ------------------------------------------------------------------------ */

  async init(): Promise<void> {
    if (this.initialized) {
      return;
    }

    if (this.initializing) {
      return this.initializing;
    }

    this.initializing =
      this.initialize();

    try {
      await this.initializing;
    } finally {
      this.initializing = null;
    }
  }

  private async initialize(): Promise<void> {
    await torrentDatabase.init();

    this.client =
      new WebTorrent({
        dht:
          torrentConfig.enableDht,

        lsd:
          torrentConfig.enableLsd,

        natUpnp:
          torrentConfig.enableUpnp,

        natPmp:
          torrentConfig.enableUpnp,

        utp: true,

        webSeeds: true,

        seedOutgoingConnections:
          true,
      });

    this.client.on(
      "error",
      (error: Error) => {
        this.emit(
          "error",
          {
            id:
              "engine",

            source:
              "",

            state:
              "error",

            error:
              error.message,

            path:
              "",

            priority:
              "normal",

            progress:
              0,

            downloaded:
              0,

            uploaded:
              0,

            downloadSpeed:
              0,

            uploadSpeed:
              0,

            ratio:
              0,

            peers:
              0,

            seeds:
              0,

            timeRemaining:
              Infinity,

            addedAt:
              Date.now(),

            updatedAt:
              Date.now(),

            retries:
              0,

            limits:
              {},
          } as TorrentRecord,
        );
      },
    );

    await this.restore();

    this.running =
      true;

    this.startWorkers();

    this.seedingManager.start();

    this.initialized =
      true;
  }

  async shutdown(): Promise<void> {
    this.running =
      false;

    this.seedingManager.stop();

    this.stopWorkers();

    await this.persistAll();

    if (this.client) {
      await new Promise<void>(
        (resolve) => {
          this.client!.destroy(
            () =>
              resolve(),
          );
        },
      );

      this.client =
        null;
    }

    await torrentDatabase.close();

    this.initialized =
      false;
  }

  /* ------------------------------------------------------------------------ */
  /* Public queries                                                            */
  /* ------------------------------------------------------------------------ */

  list(): TorrentRecord[] {
    return [
      ...this.records.values(),
    ]
      .sort(
        (
          a,
          b,
        ) =>
          b.addedAt -
          a.addedAt,
      )
      .map(
        (torrent) =>
          this.snapshot(
            torrent,
          ),
      );
  }

  get(
    id: string,
  ): TorrentRecord | undefined {
    const record =
      this.records.get(
        id,
      );

    return record
      ? this.snapshot(record)
      : undefined;
  }

  /* ------------------------------------------------------------------------ */
  /* Add                                                                       */
  /* ------------------------------------------------------------------------ */

  async add(
    source: string,
    options:
      AddTorrentOptions = {},
  ): Promise<TorrentRecord> {
    await this.init();

    if (!this.client) {
      throw new Error(
        "Torrent engine is unavailable",
      );
    }

    if (
      !source.trim()
    ) {
      throw new Error(
        "Torrent source cannot be empty",
      );
    }

    const id =
      this.generateId();

    const storagePath =
      path.resolve(
        options.path ??
          torrentConfig.dataDirectory,
      );

    await this.assertSafeStoragePath(
      storagePath,
    );

    await fs.mkdir(
      storagePath,
      {
        recursive: true,
      },
    );

    const shouldStart =
      options.startImmediately ??
      true;

    const isQueued =
      !shouldStart ||
      this.activeCount() >=
        torrentConfig.maxActive;

    const record:
      TorrentRecord = {
      id,

      source:
        source.trim(),

      path:
        storagePath,

      state:
        isQueued
          ? "queued"
          : "downloading",

      priority:
        options.priority ??
        "normal",

      progress:
        0,

      downloaded:
        0,

      uploaded:
        0,

      downloadSpeed:
        0,

      uploadSpeed:
        0,

      ratio:
        0,

      peers:
        0,

      seeds:
        0,

      timeRemaining:
        Infinity,

      addedAt:
        Date.now(),

      updatedAt:
        Date.now(),

      retries:
        0,

      limits: {
        download:
          this.normalizeLimit(
            options.downloadLimit,
          ),

        upload:
          this.normalizeLimit(
            options.uploadLimit,
          ),
      },
    };

    this.records.set(
      id,
      record,
    );

    await torrentDatabase.upsertTorrent(
      record,
    );

    if (
      options.seedingPolicy
    ) {
      this.seedingManager.setPolicy(
        id,
        options.seedingPolicy,
      );

      await torrentDatabase.upsertSeedingPolicy(
        id,
        this.seedingManager
          .getPolicy(id)
          .policy,
      );
    }

    await torrentDatabase.recordEvent(
      id,
      "added",
      {
        source:
          source.trim(),

        queued:
          isQueued,
      },
    );

    this.emit(
      "added",
      this.snapshot(record),
    );

    if (
      !isQueued
    ) {
      await this.startInternal(
        record,
        source,
      );
    }

    return this.snapshot(
      record,
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Start / Resume                                                            */
  /* ------------------------------------------------------------------------ */

  async resume(
    id: string,
  ): Promise<TorrentRecord> {
    await this.init();

    const record =
      this.require(id);

    if (
      this.torrents.has(id)
    ) {
      const torrent =
        this.torrents.get(id)!;

      torrent.resume();

      record.state =
        record.progress >= 1
          ? "seeding"
          : "downloading";

      record.updatedAt =
        Date.now();

      await this.persist(
        record,
      );

      return this.snapshot(
        record,
      );
    }

    if (
      this.activeCount() >=
      torrentConfig.maxActive
    ) {
      record.state =
        "queued";

      record.updatedAt =
        Date.now();

      await this.persist(
        record,
      );

      return this.snapshot(
        record,
      );
    }

    record.state =
      "downloading";

    record.error =
      undefined;

    record.updatedAt =
      Date.now();

    await this.startInternal(
      record,
      record.source,
    );

    return this.snapshot(
      record,
    );
  }

  async startTorrent(
    id: string,
  ): Promise<void> {
    await this.resume(
      id,
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Pause                                                                     */
  /* ------------------------------------------------------------------------ */

  async pause(
    id: string,
  ): Promise<TorrentRecord> {
    await this.init();

    const record =
      this.require(id);

    const torrent =
      this.torrents.get(
        id,
      );

    if (
      torrent
    ) {
      torrent.pause();
    }

    record.state =
      "paused";

    record.updatedAt =
      Date.now();

    await this.persist(
      record,
    );

    await torrentDatabase.recordEvent(
      id,
      "paused",
      {},
    );

    return this.snapshot(
      record,
    );
  }

  async stopTorrent(
    id: string,
  ): Promise<void> {
    await this.pause(
      id,
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Remove                                                                    */
  /* ------------------------------------------------------------------------ */

  async remove(
    id: string,
    deleteData = false,
  ): Promise<void> {
    await this.init();

    const record =
      this.require(id);

    record.state =
      "removing";

    await this.persist(
      record,
    );

    const torrent =
      this.torrents.get(
        id,
      );

    if (
      torrent &&
      this.client
    ) {
      await new Promise<void>(
        (
          resolve,
          reject,
        ) => {
          this.client!.remove(
            torrent,
            {
              destroyStore:
                deleteData,
            },
            (error) => {
              if (error) {
                reject(
                  error,
                );

                return;
              }

              resolve();
            },
          );
        },
      );
    }

    this.torrents.delete(
      id,
    );

    if (
      deleteData
    ) {
      await this.removeStorage(
        record.path,
      );
    }

    await torrentDatabase.recordEvent(
      id,
      "removed",
      {
        deleteData,
      },
    );

    await torrentDatabase.deleteTorrent(
      id,
    );

    this.records.delete(
      id,
    );

    this.seedingManager
      .deletePolicy(id);

    this.emit(
      "removed",
      {
        id,
      },
    );

    await this.fillQueue();
  }

  /* ------------------------------------------------------------------------ */
  /* Internal start                                                             */
  /* ------------------------------------------------------------------------ */

  private async startInternal(
    record: TorrentRecord,
    source: string,
  ): Promise<void> {
    if (!this.client) {
      throw new Error(
        "Torrent client unavailable",
      );
    }

    if (
      this.torrents.has(
        record.id,
      )
    ) {
      return;
    }

    await fs.mkdir(
      record.path,
      {
        recursive: true,
      },
    );

    const torrent =
      this.client.add(
        source,
        {
          path:
            record.path,
        },
        () => {
          this.onMetadata(
            record,
            torrent,
          );
        },
      );

    this.torrents.set(
      record.id,
      torrent,
    );

    this.attachTorrentListeners(
      record,
      torrent,
    );

    record.state =
      "downloading";

    record.startedAt ??=
      Date.now();

    record.updatedAt =
      Date.now();

    await this.persist(
      record,
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Torrent listeners                                                          */
  /* ------------------------------------------------------------------------ */

  private attachTorrentListeners(
    record: TorrentRecord,
    torrent: WebTorrent.Torrent,
  ): void {
    const sync =
      () => {
        this.syncRuntime(
          record,
          torrent,
        );
      };

    torrent.on(
      "download",
      sync,
    );

    torrent.on(
      "upload",
      sync,
    );

    torrent.on(
      "wire",
      sync,
    );

    torrent.on(
      "idle",
      sync,
    );

    torrent.on(
      "done",
      () => {
        void this.onCompleted(
          record,
          torrent,
        );
      },
    );

    torrent.on(
      "error",
      (error: Error) => {
        void this.onTorrentError(
          record,
          error,
        );
      },
    );

    torrent.on(
      "noPeers",
      () => {
        this.emit(
          "stalled",
          this.snapshot(
            record,
          ),
        );
      },
    );
  }

  private async onMetadata(
    record: TorrentRecord,
    torrent: WebTorrent.Torrent,
  ): Promise<void> {
    record.infoHash =
      torrent.infoHash;

    record.name =
      torrent.name;

    record.totalSize =
      torrent.length;

    record.files =
      torrent.files.map(
        (
          file,
          index,
        ) => ({
          index,

          path:
            file.path,

          name:
            file.name,

          length:
            file.length,

          progress:
            file.progress,

          selected:
            true,
        }),
      );

    record.updatedAt =
      Date.now();

    await this.persist(
      record,
    );

    await torrentDatabase
      .replaceTorrentFiles(
        record.id,
        record.files,
      );

    await torrentDatabase.recordEvent(
      record.id,
      "metadata",
      {
        name:
          record.name,

        infoHash:
          record.infoHash,

        totalSize:
          record.totalSize,
      },
    );

    this.emit(
      "metadata",
      this.snapshot(
        record,
      ),
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Completion / seeding                                                      */
  /* ------------------------------------------------------------------------ */

  private async onCompleted(
    record: TorrentRecord,
    torrent: WebTorrent.Torrent,
  ): Promise<void> {
    this.syncRuntime(
      record,
      torrent,
    );

    record.progress =
      1;

    record.completedAt ??=
      Date.now();

    record.state =
      "seeding";

    record.updatedAt =
      Date.now();

    await this.persist(
      record,
    );

    await torrentDatabase.recordEvent(
      record.id,
      "completed",
      {
        totalSize:
          record.totalSize,

        ratio:
          record.ratio,
      },
    );

    this.emit(
      "completed",
      this.snapshot(
        record,
      ),
    );

    this.emit(
      "seeding",
      this.snapshot(
        record,
      ),
    );

    await this.seedingManager
      .evaluateAll();

    await this.fillQueue();
  }

  /* ------------------------------------------------------------------------ */
  /* Errors                                                                    */
  /* ------------------------------------------------------------------------ */

  private async onTorrentError(
    record: TorrentRecord,
    error: Error,
  ): Promise<void> {
    record.state =
      "error";

    record.error =
      error.message;

    record.updatedAt =
      Date.now();

    await this.persist(
      record,
    );

    await torrentDatabase.recordEvent(
      record.id,
      "error",
      {
        message:
          error.message,
      },
    );

    this.emit(
      "error",
      this.snapshot(
        record,
      ),
    );

    this.scheduleRetry(
      record,
    );
  }

  private async scheduleRetry(
    record: TorrentRecord,
  ): Promise<void> {
    if (
      record.retries >=
      torrentConfig.maxRetries
    ) {
      return;
    }

    record.retries +=
      1;

    const delay =
      retryDelay(
        record.retries,
      );

    record.nextRetryAt =
      Date.now() +
      delay;

    await this.persist(
      record,
    );

    setTimeout(
      () => {
        void this.retry(
          record.id,
        );
      },
      delay,
    );
  }

  private async retry(
    id: string,
  ): Promise<void> {
    if (
      !this.running
    ) {
      return;
    }

    const record =
      this.records.get(
        id,
      );

    if (!record) {
      return;
    }

    if (
      this.torrents.has(id)
    ) {
      return;
    }

    if (
      this.activeCount() >=
      torrentConfig.maxActive
    ) {
      record.state =
        "queued";

      await this.persist(
        record,
      );

      return;
    }

    try {
      record.state =
        "downloading";

      record.error =
        undefined;

      record.nextRetryAt =
        undefined;

      await this.startInternal(
        record,
        record.source,
      );
    } catch (error) {
      await this.onTorrentError(
        record,
        error instanceof Error
          ? error
          : new Error(
              String(error),
            ),
      );
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Health                                                                     */
  /* ------------------------------------------------------------------------ */

  private async runHealthCheck(): Promise<void> {
    const now =
      Date.now();

    for (
      const record
        of this.records.values()
    ) {
      if (
        record.state !==
        "downloading"
      ) {
        continue;
      }

      const health =
        evaluateTorrentHealth(
          record,
          now,
          torrentConfig.stalledAfter,
        );

      if (
        !health.stalled
      ) {
        continue;
      }

      record.state =
        "stalled";

      record.stalledSince =
        now;

      record.updatedAt =
        now;

      record.error =
        health.reason;

      await this.persist(
        record,
      );

      await torrentDatabase.recordEvent(
        record.id,
        "stalled",
        {
          reason:
            health.reason,
        },
      );

      this.emit(
        "stalled",
        this.snapshot(
          record,
        ),
      );

      await this.scheduleRetry(
        record,
      );
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Queue                                                                      */
  /* ------------------------------------------------------------------------ */

  private async fillQueue(): Promise<void> {
    const queued =
      sortQueuedTorrents(
        [
          ...this.records.values(),
        ].filter(
          (torrent) =>
            torrent.state ===
            "queued",
        ),
      );

    for (
      const record of queued
    ) {
      if (
        this.activeCount() >=
        torrentConfig.maxActive
      ) {
        break;
      }

      try {
        await this.startInternal(
          record,
          record.source,
        );
      } catch (error) {
        await this.onTorrentError(
          record,
          error instanceof Error
            ? error
            : new Error(
                String(error),
              ),
        );
      }
    }
  }

  private activeCount(): number {
    let count =
      0;

    for (
      const record
        of this.records.values()
    ) {
      if (
        record.state ===
          "downloading" ||
        record.state ===
          "seeding"
      ) {
        count++;
      }
    }

    return count;
  }

  /* ------------------------------------------------------------------------ */
  /* Runtime synchronization                                                    */
  /* ------------------------------------------------------------------------ */

  private syncRuntime(
    record: TorrentRecord,
    torrent: WebTorrent.Torrent,
  ): void {
    record.progress =
      this.safeNumber(
        torrent.progress,
      );

    record.downloaded =
      this.safeNumber(
        torrent.downloaded,
      );

    record.uploaded =
      this.safeNumber(
        torrent.uploaded,
      );

    record.downloadSpeed =
      this.safeNumber(
        torrent.downloadSpeed,
      );

    record.uploadSpeed =
      this.safeNumber(
        torrent.uploadSpeed,
      );

    record.ratio =
      this.safeNumber(
        torrent.ratio,
      );

    record.peers =
      torrent.numPeers;

    record.timeRemaining =
      Number.isFinite(
        torrent.timeRemaining,
      )
        ? torrent.timeRemaining
        : Infinity;

    record.lastProgressAt =
      record.progress > 0
        ? Date.now()
        : record.lastProgressAt;

    if (
      record.downloadSpeed >
      0
    ) {
      record.lastDownloadAt =
        Date.now();
    }

    if (
      record.progress >= 1 &&
      record.state !==
        "paused"
    ) {
      record.state =
        "seeding";
    }

    record.updatedAt =
      Date.now();

    this.emit(
      "update",
      this.snapshot(
        record,
      ),
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Persistence                                                                */
  /* ------------------------------------------------------------------------ */

  private async persist(
    record: TorrentRecord,
  ): Promise<void> {
    record.updatedAt =
      Date.now();

    await torrentDatabase
      .upsertTorrent(
        record,
      );
  }

  private async persistAll(): Promise<void> {
    for (
      const record
        of this.records.values()
    ) {
      try {
        await this.persist(
          record,
        );
      } catch {
        /*
         * Do not prevent shutdown of the
         * actual torrent engine because a
         * single metadata write failed.
         */
      }
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Statistics                                                                 */
  /* ------------------------------------------------------------------------ */

  private async captureStatistics(): Promise<void> {
    if (
      this.statsWriting
    ) {
      return;
    }

    this.statsWriting =
      true;

    try {
      const active =
        [
          ...this.records.values(),
        ].filter(
          (torrent) =>
            torrent.state ===
              "downloading" ||
            torrent.state ===
              "seeding",
        );

      if (
        active.length
      ) {
        await torrentDatabase
          .insertStatistics(
            active,
          );
      }
    } finally {
      this.statsWriting =
        false;
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Workers                                                                    */
  /* ------------------------------------------------------------------------ */

  private startWorkers(): void {
    this.healthTimer =
      setInterval(
        () => {
          void this.runHealthCheck();
        },
        torrentConfig.healthInterval,
      );

    this.statisticsTimer =
      setInterval(
        () => {
          void this.captureStatistics();
        },
        torrentConfig.statisticsInterval,
      );
  }

  private stopWorkers(): void {
    if (
      this.healthTimer
    ) {
      clearInterval(
        this.healthTimer,
      );

      this.healthTimer =
        null;
    }

    if (
      this.statisticsTimer
    ) {
      clearInterval(
        this.statisticsTimer,
      );

      this.statisticsTimer =
        null;
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Restore                                                                    */
  /* ------------------------------------------------------------------------ */

  private async restore(): Promise<void> {
    /*
     * Scylla is partition-oriented. The current database
     * schema intentionally uses torrent_id as the primary
     * key for the torrent registry, so restoration needs
     * an external ID index/table for very large fleets.
     *
     * For a small/medium registry, a dedicated registry
     * listing table should be queried here.
     *
     * This method is intentionally isolated so the
     * registry strategy can scale independently.
     */
  }

  /* ------------------------------------------------------------------------ */
  /* Storage                                                                    */
  /* ------------------------------------------------------------------------ */

  private async assertSafeStoragePath(
    storagePath: string,
  ): Promise<void> {
    const root =
      path.resolve(
        torrentConfig.dataDirectory,
      );

    const target =
      path.resolve(
        storagePath,
      );

    if (
      target !== root &&
      !target.startsWith(
        `${root}${path.sep}`,
      )
    ) {
      throw new Error(
        "Torrent storage path is outside the configured storage root",
      );
    }
  }

  private async removeStorage(
    storagePath: string,
  ): Promise<void> {
    await this.assertSafeStoragePath(
      storagePath,
    );

    await fs.rm(
      storagePath,
      {
        recursive: true,
        force: true,
      },
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Helpers                                                                    */
  /* ------------------------------------------------------------------------ */

  private require(
    id: string,
  ): TorrentRecord {
    const record =
      this.records.get(
        id,
      );

    if (!record) {
      throw new Error(
        `Torrent ${id} was not found`,
      );
    }

    return record;
  }

  private snapshot(
    record: TorrentRecord,
  ): TorrentRecord {
    return {
      ...record,

      limits: {
        ...record.limits,
      },

      files:
        record.files
          ? record.files.map(
              (file) => ({
                ...file,
              }),
            )
          : undefined,
    };
  }

  private safeNumber(
    value: unknown,
  ): number {
    return typeof value === "number" &&
      Number.isFinite(value)
      ? value
      : 0;
  }

  private normalizeLimit(
    value: number | undefined,
  ): number {
    if (
      value === undefined ||
      !Number.isFinite(value) ||
      value < 0
    ) {
      return 0;
    }

    return Math.floor(
      value,
    );
  }

  private generateId(): string {
    return [
      Date.now().toString(36),
      Math.random()
        .toString(36)
        .slice(2, 12),
    ].join("-");
  }
}

/* -------------------------------------------------------------------------- */
/* Singleton                                                                   */
/* -------------------------------------------------------------------------- */

declare global {
  // eslint-disable-next-line no-var
  var __lunarTorrentManager:
    | TorrentManager
    | undefined;
}

export const torrentManager =
  globalThis
    .__lunarTorrentManager ??
  (globalThis.__lunarTorrentManager =
    new TorrentManager());
