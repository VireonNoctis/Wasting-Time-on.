// src/lib/database.ts

import {
  Client,
  types,
  auth,
} from "cassandra-driver";

import type {
  TorrentPriority,
  TorrentRecord,
  TorrentState,
} from "./torrent-types";

import type {
  SeedStopReason,
  SeedingPolicy,
  SeedingRuntime,
} from "./seeding-types";

/* -------------------------------------------------------------------------- */
/* Types                                                                      */
/* -------------------------------------------------------------------------- */

export interface DatabaseConfig {
  contactPoints: string[];
  localDataCenter: string;

  username?: string;
  password?: string;

  keyspace: string;

  replicationFactor: number;

  protocolOptions?: {
    port?: number;
  };

  socketOptions?: {
    connectTimeout?: number;
    readTimeout?: number;
  };

  queryOptions?: {
    prepare?: boolean;
  };
}

export interface TorrentRow {
  torrent_id: string;

  source: string;

  info_hash: string | null;
  name: string | null;

  storage_path: string;

  state: string;
  priority: string;

  progress: number;

  downloaded: number;
  uploaded: number;

  download_speed: number;
  upload_speed: number;

  ratio: number;

  peers: number;
  seeds: number;

  time_remaining: number | null;

  total_size: number | null;

  added_at: Date;
  started_at: Date | null;
  completed_at: Date | null;
  updated_at: Date;

  last_progress_at: Date | null;
  last_download_at: Date | null;

  stalled_since: Date | null;

  retries: number;

  next_retry_at: Date | null;

  download_limit: number;
  upload_limit: number;

  error: string | null;
}

export interface TorrentFileRow {
  torrent_id: string;
  file_index: number;

  file_path: string;
  file_name: string;

  length: number;

  progress: number;
  selected: boolean;
}

export interface SeedPolicyRow {
  torrent_id: string;

  enabled: boolean;

  mode: string;

  target_ratio: number | null;

  max_seed_time: number | null;
  min_seed_time: number | null;

  ratio_requires_peers: boolean;

  max_peers: number | null;
  idle_timeout: number | null;

  min_peers: number | null;

  priority: number;
  pinned: boolean;
  force_seed: boolean;

  schedule_days: number[] | null;

  schedule_timezone: string | null;

  schedule_start_hour: number | null;
  schedule_start_minute: number | null;

  schedule_end_hour: number | null;
  schedule_end_minute: number | null;
}

export interface SeedRuntimeRow {
  torrent_id: string;

  started_at: Date | null;

  total_seed_time: number;

  last_peer_at: Date | null;
  last_upload_at: Date | null;
  last_evaluation_at: Date | null;

  consecutive_high_peer_checks: number;

  stop_reason: string | null;

  currently_seeding: boolean;

  updated_at: Date;
}

export interface TorrentStatsRow {
  bucket: Date;

  torrent_id: string;
  captured_at: Date;

  progress: number;

  download_speed: number;
  upload_speed: number;

  downloaded: number;
  uploaded: number;

  peers: number;
  seeds: number;
}

export interface TorrentEventRow {
  torrent_id: string;

  event_date: Date;
  event_id: string;

  event_type: string;

  payload: string;
}

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

function envNumber(
  name: string,
  fallback: number,
): number {
  const value =
    Number(process.env[name]);

  return Number.isFinite(value)
    ? value
    : fallback;
}

function parseContactPoints(): string[] {
  const value =
    process.env.SCYLLA_CONTACT_POINTS ||
    process.env.SCYLLA_HOSTS ||
    "127.0.0.1";

  return value
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);
}

function dateOrNull(
  value: unknown,
): Date | null {
  return value instanceof Date
    ? value
    : null;
}

function numberOrZero(
  value: unknown,
): number {
  return typeof value === "number" &&
    Number.isFinite(value)
    ? value
    : 0;
}

function boolValue(
  value: unknown,
): boolean {
  return value === true;
}

function stringOrNull(
  value: unknown,
): string | null {
  return typeof value === "string"
    ? value
    : null;
}

/* -------------------------------------------------------------------------- */
/* Database                                                                   */
/* -------------------------------------------------------------------------- */

export class TorrentDatabase {
  private readonly config: DatabaseConfig;

  private client: Client | null = null;

  private initialized = false;

  private initializing:
    Promise<void> | null = null;

  private readonly statements = {
    insertTorrent:
      `
      INSERT INTO lunar_torrent.torrents (
        torrent_id,
        source,
        info_hash,
        name,
        storage_path,
        state,
        priority,
        progress,
        downloaded,
        uploaded,
        download_speed,
        upload_speed,
        ratio,
        peers,
        seeds,
        time_remaining,
        total_size,
        added_at,
        started_at,
        completed_at,
        updated_at,
        last_progress_at,
        last_download_at,
        stalled_since,
        retries,
        next_retry_at,
        download_limit,
        upload_limit,
        error
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,

    getTorrent:
      `
      SELECT *
      FROM lunar_torrent.torrents
      WHERE torrent_id = ?
      `,

    deleteTorrent:
      `
      DELETE FROM lunar_torrent.torrents
      WHERE torrent_id = ?
      `,

    insertFile:
      `
      INSERT INTO lunar_torrent.torrent_files (
        torrent_id,
        file_index,
        file_path,
        file_name,
        length,
        progress,
        selected
      )
      VALUES (?, ?, ?, ?, ?, ?, ?)
      `,

    getFiles:
      `
      SELECT *
      FROM lunar_torrent.torrent_files
      WHERE torrent_id = ?
      `,

    deleteFiles:
      `
      DELETE FROM lunar_torrent.torrent_files
      WHERE torrent_id = ?
      `,

    insertSeedPolicy:
      `
      INSERT INTO lunar_torrent.seeding_policies (
        torrent_id,
        enabled,
        mode,
        target_ratio,
        max_seed_time,
        min_seed_time,
        ratio_requires_peers,
        max_peers,
        idle_timeout,
        min_peers,
        priority,
        pinned,
        force_seed,
        schedule_days,
        schedule_timezone,
        schedule_start_hour,
        schedule_start_minute,
        schedule_end_hour,
        schedule_end_minute
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,

    getSeedPolicy:
      `
      SELECT *
      FROM lunar_torrent.seeding_policies
      WHERE torrent_id = ?
      `,

    deleteSeedPolicy:
      `
      DELETE FROM lunar_torrent.seeding_policies
      WHERE torrent_id = ?
      `,

    insertSeedRuntime:
      `
      INSERT INTO lunar_torrent.seeding_runtime (
        torrent_id,
        started_at,
        total_seed_time,
        last_peer_at,
        last_upload_at,
        last_evaluation_at,
        consecutive_high_peer_checks,
        stop_reason,
        currently_seeding,
        updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,

    getSeedRuntime:
      `
      SELECT *
      FROM lunar_torrent.seeding_runtime
      WHERE torrent_id = ?
      `,

    insertStat:
      `
      INSERT INTO lunar_torrent.torrent_stats (
        torrent_id,
        bucket,
        captured_at,
        progress,
        download_speed,
        upload_speed,
        downloaded,
        uploaded,
        peers,
        seeds
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,

    insertEvent:
      `
      INSERT INTO lunar_torrent.torrent_events (
        torrent_id,
        event_date,
        event_id,
        event_type,
        payload
      )
      VALUES (?, ?, ?, ?, ?)
      `,

    getStats:
      `
      SELECT *
      FROM lunar_torrent.torrent_stats
      WHERE torrent_id = ?
        AND bucket >= ?
        AND bucket <= ?
      `,

    getEvents:
      `
      SELECT *
      FROM lunar_torrent.torrent_events
      WHERE torrent_id = ?
        AND event_date >= ?
        AND event_date <= ?
      `,

    getSetting:
      `
      SELECT setting_value
      FROM lunar_torrent.settings
      WHERE setting_key = ?
      `,

    setSetting:
      `
      INSERT INTO lunar_torrent.settings (
        setting_key,
        setting_value,
        updated_at
      )
      VALUES (?, ?, ?)
      `,
  };

  constructor(
    config?: Partial<DatabaseConfig>,
  ) {
    this.config = {
      contactPoints:
        config?.contactPoints ??
        parseContactPoints(),

      localDataCenter:
        config?.localDataCenter ??
        process.env.SCYLLA_DATACENTER ??
        "datacenter1",

      username:
        config?.username ??
        process.env.SCYLLA_USERNAME,

      password:
        config?.password ??
        process.env.SCYLLA_PASSWORD,

      keyspace:
        config?.keyspace ??
        process.env.SCYLLA_KEYSPACE ??
        "lunar_torrent",

      replicationFactor:
        config?.replicationFactor ??
        envNumber(
          "SCYLLA_REPLICATION_FACTOR",
          3,
        ),

      protocolOptions:
        config?.protocolOptions,

      socketOptions:
        config?.socketOptions,

      queryOptions: {
        prepare: true,
        ...config?.queryOptions,
      },
    };
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
    const clusterConfig: ConstructorParameters<
      typeof Client
    >[0] = {
      contactPoints:
        this.config.contactPoints,

      localDataCenter:
        this.config.localDataCenter,

      ...(this.config.protocolOptions
        ? {
            protocolOptions:
              this.config.protocolOptions,
          }
        : {}),

      ...(this.config.socketOptions
        ? {
            socketOptions:
              this.config.socketOptions,
          }
        : {}),
    };

    if (
      this.config.username &&
      this.config.password
    ) {
      clusterConfig.authProvider =
        new auth.PlainTextAuthProvider(
          this.config.username,
          this.config.password,
        );
    }

    /*
     * Connect without selecting the application
     * keyspace first so we can create it if necessary.
     */
    const bootstrap =
      new Client(
        clusterConfig,
      );

    await bootstrap.connect();

    await bootstrap.execute(
      `
      CREATE KEYSPACE IF NOT EXISTS ${this.safeIdentifier(
        this.config.keyspace,
      )}
      WITH replication = {
        'class': 'NetworkTopologyStrategy',
        '${this.config.localDataCenter}': ${this.config.replicationFactor}
      }
      `,
    );

    await bootstrap.shutdown();

    this.client =
      new Client({
        ...clusterConfig,
        keyspace:
          this.config.keyspace,
      });

    await this.client.connect();

    await this.createSchema();

    this.initialized = true;
  }

  async close(): Promise<void> {
    if (!this.client) {
      return;
    }

    const client =
      this.client;

    this.client = null;
    this.initialized = false;

    await client.shutdown();
  }

  async health(): Promise<{
    healthy: boolean;
    latencyMs?: number;
    error?: string;
  }> {
    const started =
      Date.now();

    try {
      await this.init();

      await this.client!.execute(
        "SELECT release_version FROM system.local",
      );

      return {
        healthy: true,
        latencyMs:
          Date.now() - started,
      };
    } catch (error) {
      return {
        healthy: false,
        latencyMs:
          Date.now() - started,
        error:
          error instanceof Error
            ? error.message
            : String(error),
      };
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Schema                                                                   */
  /* ------------------------------------------------------------------------ */

  private async createSchema(): Promise<void> {
    const queries = [
      `
      CREATE TABLE IF NOT EXISTS torrents (
        torrent_id text PRIMARY KEY,

        source text,

        info_hash text,
        name text,

        storage_path text,

        state text,
        priority text,

        progress double,

        downloaded bigint,
        uploaded bigint,

        download_speed bigint,
        upload_speed bigint,

        ratio double,

        peers int,
        seeds int,

        time_remaining bigint,
        total_size bigint,

        added_at timestamp,
        started_at timestamp,
        completed_at timestamp,
        updated_at timestamp,

        last_progress_at timestamp,
        last_download_at timestamp,

        stalled_since timestamp,

        retries int,

        next_retry_at timestamp,

        download_limit bigint,
        upload_limit bigint,

        error text
      )
      `,

      `
      CREATE TABLE IF NOT EXISTS torrent_files (
        torrent_id text,
        file_index int,

        file_path text,
        file_name text,

        length bigint,

        progress double,
        selected boolean,

        PRIMARY KEY (
          torrent_id,
          file_index
        )
      )
      `,

      `
      CREATE TABLE IF NOT EXISTS seeding_policies (
        torrent_id text PRIMARY KEY,

        enabled boolean,

        mode text,

        target_ratio double,

        max_seed_time bigint,
        min_seed_time bigint,

        ratio_requires_peers boolean,

        max_peers int,
        idle_timeout bigint,

        min_peers int,

        priority int,

        pinned boolean,
        force_seed boolean,

        schedule_days list<int>,
        schedule_timezone text,

        schedule_start_hour int,
        schedule_start_minute int,

        schedule_end_hour int,
        schedule_end_minute int
      )
      `,

      `
      CREATE TABLE IF NOT EXISTS seeding_runtime (
        torrent_id text PRIMARY KEY,

        started_at timestamp,

        total_seed_time bigint,

        last_peer_at timestamp,
        last_upload_at timestamp,
        last_evaluation_at timestamp,

        consecutive_high_peer_checks int,

        stop_reason text,

        currently_seeding boolean,

        updated_at timestamp
      )
      `,

      `
      CREATE TABLE IF NOT EXISTS torrent_stats (
        torrent_id text,
        bucket timestamp,

        captured_at timestamp,

        progress double,

        download_speed bigint,
        upload_speed bigint,

        downloaded bigint,
        uploaded bigint,

        peers int,
        seeds int,

        PRIMARY KEY (
          (torrent_id, bucket),
          captured_at
        )
      ) WITH CLUSTERING ORDER BY (
        captured_at DESC
      )
      `,

      `
      CREATE TABLE IF NOT EXISTS torrent_events (
        torrent_id text,
        event_date timestamp,
        event_id timeuuid,

        event_type text,
        payload text,

        PRIMARY KEY (
          (torrent_id, event_date),
          event_id
        )
      ) WITH CLUSTERING ORDER BY (
        event_id DESC
      )
      `,

      `
      CREATE TABLE IF NOT EXISTS settings (
        setting_key text PRIMARY KEY,
        setting_value text,
        updated_at timestamp
      )
      `,
    ];

    for (const query of queries) {
      await this.client!.execute(
        query,
      );
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Torrents                                                                 */
  /* ------------------------------------------------------------------------ */

  async upsertTorrent(
    torrent: TorrentRecord,
  ): Promise<void> {
    await this.init();

    await this.execute(
      this.statements.insertTorrent,
      [
        torrent.id,
        torrent.source,

        torrent.infoHash ?? null,
        torrent.name ?? null,

        torrent.path,

        torrent.state,
        torrent.priority,

        torrent.progress,

        types.Long.fromNumber(
          Math.max(
            0,
            Math.floor(
              torrent.downloaded,
            ),
          ),
        ),

        types.Long.fromNumber(
          Math.max(
            0,
            Math.floor(
              torrent.uploaded,
            ),
          ),
        ),

        types.Long.fromNumber(
          Math.max(
            0,
            Math.floor(
              torrent.downloadSpeed,
            ),
          ),
        ),

        types.Long.fromNumber(
          Math.max(
            0,
            Math.floor(
              torrent.uploadSpeed,
            ),
          ),
        ),

        torrent.ratio,

        torrent.peers,
        torrent.seeds,

        Number.isFinite(
          torrent.timeRemaining,
        )
          ? types.Long.fromNumber(
              Math.floor(
                torrent.timeRemaining,
              ),
            )
          : null,

        torrent.totalSize !== undefined
          ? types.Long.fromNumber(
              Math.floor(
                torrent.totalSize,
              ),
            )
          : null,

        new Date(
          torrent.addedAt,
        ),

        torrent.startedAt
          ? new Date(
              torrent.startedAt,
            )
          : null,

        torrent.completedAt
          ? new Date(
              torrent.completedAt,
            )
          : null,

        new Date(
          torrent.updatedAt,
        ),

        torrent.lastProgressAt
          ? new Date(
              torrent.lastProgressAt,
            )
          : null,

        torrent.lastDownloadAt
          ? new Date(
              torrent.lastDownloadAt,
            )
          : null,

        torrent.stalledSince
          ? new Date(
              torrent.stalledSince,
            )
          : null,

        torrent.retries,

        torrent.nextRetryAt
          ? new Date(
              torrent.nextRetryAt,
            )
          : null,

        types.Long.fromNumber(
          Math.max(
            0,
            Math.floor(
              torrent.limits
                .download ?? 0,
            ),
          ),
        ),

        types.Long.fromNumber(
          Math.max(
            0,
            Math.floor(
              torrent.limits
                .upload ?? 0,
            ),
          ),
        ),

        torrent.error ?? null,
      ],
    );
  }

  async getTorrent(
    torrentId: string,
  ): Promise<
    TorrentRecord | null
  > {
    await this.init();

    const result =
      await this.execute(
        this.statements.getTorrent,
        [torrentId],
      );

    const row =
      result.rows[0] as
        | TorrentRow
        | undefined;

    if (!row) {
      return null;
    }

    return this.mapTorrentRow(
      row,
    );
  }

  async deleteTorrent(
    torrentId: string,
  ): Promise<void> {
    await this.init();

    await this.execute(
      this.statements.deleteTorrent,
      [torrentId],
    );

    await this.deleteTorrentFiles(
      torrentId,
    );

    await this.deleteSeedPolicy(
      torrentId,
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Torrent Files                                                             */
  /* ------------------------------------------------------------------------ */

  async replaceTorrentFiles(
    torrentId: string,
    files: TorrentRecord["files"],
  ): Promise<void> {
    await this.init();

    await this.execute(
      this.statements.deleteFiles,
      [torrentId],
    );

    if (!files?.length) {
      return;
    }

    const queries =
      files.map((file) => ({
        query:
          this.statements.insertFile,
        params: [
          torrentId,
          file.index,
          file.path,
          file.name,
          types.Long.fromNumber(
            Math.floor(
              file.length,
            ),
          ),
          file.progress,
          file.selected,
        ],
      }));

    /*
     * All file rows for one torrent share
     * the same partition key, making this a
     * good candidate for a small batch.
     */
    await this.client!.batch(
      queries,
      {
        prepare: true,
        logged: false,
      },
    );
  }

  async getTorrentFiles(
    torrentId: string,
  ): Promise<
    NonNullable<
      TorrentRecord["files"]
    >
  > {
    await this.init();

    const result =
      await this.execute(
        this.statements.getFiles,
        [torrentId],
      );

    return result.rows.map(
      (row) => ({
        index:
          Number(
            row.file_index,
          ),

        path:
          String(
            row.file_path,
          ),

        name:
          String(
            row.file_name,
          ),

        length:
          this.longToNumber(
            row.length,
          ),

        progress:
          numberOrZero(
            row.progress,
          ),

        selected:
          boolValue(
            row.selected,
          ),
      }),
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Seeding Policies                                                          */
  /* ------------------------------------------------------------------------ */

  async upsertSeedingPolicy(
    torrentId: string,
    policy: SeedingPolicy,
  ): Promise<void> {
    await this.init();

    const schedule =
      policy.schedule;

    await this.execute(
      this.statements.insertSeedPolicy,
      [
        torrentId,

        policy.enabled,

        policy.mode,

        policy.targetRatio ??
          null,

        policy.maxSeedTime ??
          null,

        policy.minSeedTime ??
          null,

        policy.ratioRequiresPeers ??
          false,

        policy.maxPeers ??
          null,

        policy.idleTimeout ??
          null,

        policy.minPeers ??
          null,

        policy.priority ??
          0,

        policy.pinned ??
          false,

        policy.forceSeed ??
          false,

        schedule?.days ??
          null,

        schedule?.timezone ??
          null,

        schedule?.startHour ??
          null,

        schedule?.startMinute ??
          null,

        schedule?.endHour ??
          null,

        schedule?.endMinute ??
          null,
      ],
    );
  }

  async getSeedingPolicy(
    torrentId: string,
  ): Promise<
    SeedingPolicy | null
  > {
    await this.init();

    const result =
      await this.execute(
        this.statements.getSeedPolicy,
        [torrentId],
      );

    const row =
      result.rows[0] as
        | SeedPolicyRow
        | undefined;

    if (!row) {
      return null;
    }

    return {
      enabled:
        boolValue(
          row.enabled,
        ),

      mode:
        row.mode as SeedingPolicy["mode"],

      targetRatio:
        row.target_ratio ??
        undefined,

      maxSeedTime:
        this.longToNumberNullable(
          row.max_seed_time,
        ),

      minSeedTime:
        this.longToNumberNullable(
          row.min_seed_time,
        ),

      ratioRequiresPeers:
        boolValue(
          row.ratio_requires_peers,
        ),

      maxPeers:
        row.max_peers ??
        undefined,

      idleTimeout:
        this.longToNumberNullable(
          row.idle_timeout,
        ),

      minPeers:
        row.min_peers ??
        undefined,

      priority:
        numberOrZero(
          row.priority,
        ),

      pinned:
        boolValue(
          row.pinned,
        ),

      forceSeed:
        boolValue(
          row.force_seed,
        ),

      schedule:
        row.schedule_days &&
        row.schedule_start_hour !==
          null &&
        row.schedule_start_minute !==
          null &&
        row.schedule_end_hour !==
          null &&
        row.schedule_end_minute !==
          null
          ? {
              timezone:
                row.schedule_timezone ??
                undefined,

              days:
                row.schedule_days,

              startHour:
                row.schedule_start_hour,

              startMinute:
                row.schedule_start_minute,

              endHour:
                row.schedule_end_hour,

              endMinute:
                row.schedule_end_minute,
            }
          : undefined,
    };
  }

  async deleteSeedPolicy(
    torrentId: string,
  ): Promise<void> {
    await this.init();

    await this.execute(
      this.statements.deleteSeedPolicy,
      [torrentId],
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Seeding Runtime                                                           */
  /* ------------------------------------------------------------------------ */

  async upsertSeedingRuntime(
    torrentId: string,
    runtime: SeedingRuntime,
  ): Promise<void> {
    await this.init();

    await this.execute(
      this.statements.insertSeedRuntime,
      [
        torrentId,

        runtime.startedAt
          ? new Date(
              runtime.startedAt,
            )
          : null,

        types.Long.fromNumber(
          Math.floor(
            runtime.totalSeedTime,
          ),
        ),

        runtime.lastPeerAt
          ? new Date(
              runtime.lastPeerAt,
            )
          : null,

        runtime.lastUploadAt
          ? new Date(
              runtime.lastUploadAt,
            )
          : null,

        runtime.lastEvaluationAt
          ? new Date(
              runtime.lastEvaluationAt,
            )
          : null,

        runtime
          .consecutiveHighPeerChecks,

        runtime.stopReason ??
          null,

        runtime.currentlySeeding,

        new Date(),
      ],
    );
  }

  async getSeedingRuntime(
    torrentId: string,
  ): Promise<
    SeedingRuntime | null
  > {
    await this.init();

    const result =
      await this.execute(
        this.statements.getSeedRuntime,
        [torrentId],
      );

    const row =
      result.rows[0] as
        | SeedRuntimeRow
        | undefined;

    if (!row) {
      return null;
    }

    return {
      startedAt:
        dateOrNull(
          row.started_at,
        )?.getTime(),

      totalSeedTime:
        this.longToNumber(
          row.total_seed_time,
        ),

      lastPeerAt:
        dateOrNull(
          row.last_peer_at,
        )?.getTime(),

      lastUploadAt:
        dateOrNull(
          row.last_upload_at,
        )?.getTime(),

      lastEvaluationAt:
        dateOrNull(
          row.last_evaluation_at,
        )?.getTime(),

      consecutiveHighPeerChecks:
        numberOrZero(
          row.consecutive_high_peer_checks,
        ),

      stopReason:
        stringOrNull(
          row.stop_reason,
        ) as
          | SeedStopReason
          | undefined,

      currentlySeeding:
        boolValue(
          row.currently_seeding,
        ),
    };
  }

  /* ------------------------------------------------------------------------ */
  /* Statistics                                                                */
  /* ------------------------------------------------------------------------ */

  async insertStatistic(
    torrent: TorrentRecord,
    capturedAt = new Date(),
  ): Promise<void> {
    await this.init();

    const bucket =
      new Date(
        Math.floor(
          capturedAt.getTime() /
            60_000,
        ) *
          60_000,
      );

    await this.execute(
      this.statements.insertStat,
      [
        torrent.id,

        bucket,

        capturedAt,

        torrent.progress,

        types.Long.fromNumber(
          Math.floor(
            torrent.downloadSpeed,
          ),
        ),

        types.Long.fromNumber(
          Math.floor(
            torrent.uploadSpeed,
          ),
        ),

        types.Long.fromNumber(
          Math.floor(
            torrent.downloaded,
          ),
        ),

        types.Long.fromNumber(
          Math.floor(
            torrent.uploaded,
          ),
        ),

        torrent.peers,
        torrent.seeds,
      ],
    );
  }

  async insertStatistics(
    torrents: TorrentRecord[],
  ): Promise<void> {
    await this.init();

    if (!torrents.length) {
      return;
    }

    const capturedAt =
      new Date();

    const bucket =
      new Date(
        Math.floor(
          capturedAt.getTime() /
            60_000,
        ) *
          60_000,
      );

    /*
     * Intentionally use a small, unlogged batch.
     * Large cross-partition batches should be avoided;
     * individual writes can also be executed concurrently
     * when higher throughput is required.
     */
    const queries =
      torrents.map(
        (torrent) => ({
          query:
            this.statements.insertStat,

          params: [
            torrent.id,

            bucket,

            capturedAt,

            torrent.progress,

            types.Long.fromNumber(
              Math.floor(
                torrent.downloadSpeed,
              ),
            ),

            types.Long.fromNumber(
              Math.floor(
                torrent.uploadSpeed,
              ),
            ),

            types.Long.fromNumber(
              Math.floor(
                torrent.downloaded,
              ),
            ),

            types.Long.fromNumber(
              Math.floor(
                torrent.uploaded,
              ),
            ),

            torrent.peers,
            torrent.seeds,
          ],
        }),
      );

    await this.client!.batch(
      queries,
      {
        prepare: true,
        logged: false,
      },
    );
  }

  async getStatistics(
    torrentId: string,
    from: Date,
    to: Date,
  ): Promise<TorrentStatsRow[]> {
    await this.init();

    const result =
      await this.execute(
        this.statements.getStats,
        [
          torrentId,
          from,
          to,
        ],
      );

    return result.rows.map(
      (row) =>
        row as TorrentStatsRow,
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Events                                                                    */
  /* ------------------------------------------------------------------------ */

  async recordEvent(
    torrentId: string,
    type: string,
    payload: unknown,
  ): Promise<void> {
    await this.init();

    await this.execute(
      this.statements.insertEvent,
      [
        torrentId,
        new Date(),
        types.Uuid.random(),

        type,

        JSON.stringify(
          payload,
        ),
      ],
    );
  }

  async getEvents(
    torrentId: string,
    from: Date,
    to: Date,
  ): Promise<TorrentEventRow[]> {
    await this.init();

    const result =
      await this.execute(
        this.statements.getEvents,
        [
          torrentId,
          from,
          to,
        ],
      );

    return result.rows.map(
      (row) =>
        row as TorrentEventRow,
    );
  }

  /* ------------------------------------------------------------------------ */
  /* Settings                                                                  */
  /* ------------------------------------------------------------------------ */

  async setSetting(
    key: string,
    value: unknown,
  ): Promise<void> {
    await this.init();

    await this.execute(
      this.statements.setSetting,
      [
        key,
        JSON.stringify(
          value,
        ),
        new Date(),
      ],
    );
  }

  async getSetting<T>(
    key: string,
  ): Promise<T | null> {
    await this.init();

    const result =
      await this.execute(
        this.statements.getSetting,
        [key],
      );

    const raw =
      result.rows[0]
        ?.setting_value;

    if (
      typeof raw !== "string"
    ) {
      return null;
    }

    try {
      return JSON.parse(
        raw,
      ) as T;
    } catch {
      return raw as T;
    }
  }

  /* ------------------------------------------------------------------------ */
  /* Query execution                                                           */
  /* ------------------------------------------------------------------------ */

  private async execute(
    query: string,
    params: unknown[],
  ): Promise<{
    rows: Record<
      string,
      any
    >[];
  }> {
    await this.init();

    let lastError:
      | unknown
      | undefined;

    const maxAttempts = 3;

    for (
      let attempt = 1;
      attempt <= maxAttempts;
      attempt++
    ) {
      try {
        return await this.client!.execute(
          query,
          params,
          {
            prepare:
              this.config
                .queryOptions
                ?.prepare ??
              true,
          },
        );
      } catch (error) {
        lastError = error;

        if (
          attempt ===
          maxAttempts
        ) {
          break;
        }

        await this.sleep(
          100 *
            Math.pow(
              2,
              attempt - 1,
            ),
        );
      }
    }

    throw lastError;
  }

  /* ------------------------------------------------------------------------ */
  /* Mapping                                                                   */
  /* ------------------------------------------------------------------------ */

  private mapTorrentRow(
    row: TorrentRow,
  ): TorrentRecord {
    return {
      id:
        row.torrent_id,

      source:
        row.source,

      infoHash:
        row.info_hash ??
        undefined,

      name:
        row.name ??
        undefined,

      path:
        row.storage_path,

      state:
        row.state as TorrentState,

      priority:
        row.priority as TorrentPriority,

      progress:
        numberOrZero(
          row.progress,
        ),

      downloaded:
        this.longToNumber(
          row.downloaded,
        ),

      uploaded:
        this.longToNumber(
          row.uploaded,
        ),

      downloadSpeed:
        this.longToNumber(
          row.download_speed,
        ),

      uploadSpeed:
        this.longToNumber(
          row.upload_speed,
        ),

      ratio:
        numberOrZero(
          row.ratio,
        ),

      peers:
        numberOrZero(
          row.peers,
        ),

      seeds:
        numberOrZero(
          row.seeds,
        ),

      timeRemaining:
        row.time_remaining
          ? this.longToNumber(
              row.time_remaining,
            )
          : Infinity,

      totalSize:
        row.total_size
          ? this.longToNumber(
              row.total_size,
            )
          : undefined,

      addedAt:
        row.added_at.getTime(),

      startedAt:
        row.started_at?.getTime(),

      completedAt:
        row.completed_at?.getTime(),

      updatedAt:
        row.updated_at.getTime(),

      lastProgressAt:
        row.last_progress_at?.getTime(),

      lastDownloadAt:
        row.last_download_at?.getTime(),

      stalledSince:
        row.stalled_since?.getTime(),

      retries:
        numberOrZero(
          row.retries,
        ),

      nextRetryAt:
        row.next_retry_at?.getTime(),

      limits: {
        download:
          this.longToNumber(
            row.download_limit,
          ),

        upload:
          this.longToNumber(
            row.upload_limit,
          ),
      },

      error:
        row.error ??
        undefined,
    };
  }

  private longToNumber(
    value: unknown,
  ): number {
    if (
      typeof value ===
      "number"
    ) {
      return value;
    }

    if (
      types.Long.isLong(
        value,
      )
    ) {
      return value.toNumber();
    }

    return 0;
  }

  private longToNumberNullable(
    value: unknown,
  ): number | undefined {
    if (
      value === null ||
      value === undefined
    ) {
      return undefined;
    }

    return this.longToNumber(
      value,
    );
  }

  private safeIdentifier(
    identifier: string,
  ): string {
    if (
      !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(
        identifier,
      )
    ) {
      throw new Error(
        `Unsafe CQL identifier: ${identifier}`,
      );
    }

    return identifier;
  }

  private async sleep(
    ms: number,
  ): Promise<void> {
    await new Promise<void>(
      (resolve) =>
        setTimeout(
          resolve,
          ms,
        ),
    );
  }
}

/* -------------------------------------------------------------------------- */
/* Singleton                                                                   */
/* -------------------------------------------------------------------------- */

declare global {
  // eslint-disable-next-line no-var
  var __lunarTorrentDatabase:
    | TorrentDatabase
    | undefined;
}

export const torrentDatabase =
  globalThis
    .__lunarTorrentDatabase ??
  (globalThis.__lunarTorrentDatabase =
    new TorrentDatabase());
