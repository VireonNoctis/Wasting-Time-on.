export type SeedStopReason =
  | "manual"
  | "ratio-reached"
  | "time-reached"
  | "idle-timeout"
  | "peer-limit"
  | "schedule"
  | "disk-pressure"
  | "disabled";

export type SeedingMode =
  | "always"
  | "ratio"
  | "time"
  | "ratio-or-time"
  | "ratio-and-time"
  | "peers"
  | "until-disabled"
  | "scheduled";

export interface SeedingPolicy {
  enabled: boolean;

  mode: SeedingMode;

  /**
   * Uploaded / downloaded.
   * Example: 2 = upload twice the downloaded amount.
   */
  targetRatio?: number;

  /**
   * Maximum seed duration in milliseconds.
   */
  maxSeedTime?: number;

  /**
   * Minimum seed duration in milliseconds.
   */
  minSeedTime?: number;

  /**
   * If true, the torrent can stop after reaching
   * the ratio even if the peer count is zero.
   */
  ratioRequiresPeers?: boolean;

  /**
   * Stop once peer count stays above this number
   * for the configured number of checks.
   */
  maxPeers?: number;

  /**
   * Stop if the torrent has had zero peers for
   * this duration.
   */
  idleTimeout?: number;

  /**
   * Minimum number of peers we'd like to preserve
   * before allowing some automatic policies to stop.
   */
  minPeers?: number;

  /**
   * Optional schedule.
   */
  schedule?: SeedSchedule;

  /**
   * Priority used by the seed-slot scheduler.
   */
  priority?: number;

  /**
   * Whether this torrent gets a permanent seeding slot.
   */
  pinned?: boolean;

  /**
   * Prevent automatic stopping.
   */
  forceSeed?: boolean;
}

export interface SeedSchedule {
  timezone?: string;

  days: number[];

  startHour: number;
  startMinute: number;

  endHour: number;
  endMinute: number;
}

export interface SeedingRuntime {
  startedAt?: number;

  totalSeedTime: number;

  lastPeerAt?: number;
  lastUploadAt?: number;

  lastEvaluationAt?: number;

  consecutiveHighPeerChecks: number;

  stopReason?: SeedStopReason;

  currentlySeeding: boolean;
}

export interface SeedingRecord {
  torrentId: string;

  policy: SeedingPolicy;

  runtime: SeedingRuntime;
}
