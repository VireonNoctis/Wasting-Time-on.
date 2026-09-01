export type TorrentState =
  | "queued"
  | "downloading"
  | "seeding"
  | "paused"
  | "completed"
  | "stalled"
  | "error"
  | "checking"
  | "removing";

export type TorrentPriority =
  | "low"
  | "normal"
  | "high"
  | "critical";

export interface TorrentLimits {
  download?: number;
  upload?: number;
}

export interface TorrentFile {
  index: number;
  path: string;
  name: string;
  length: number;
  progress: number;
  selected: boolean;
}

export interface TorrentRecord {
  id: string;
  source: string;

  infoHash?: string;
  name?: string;

  path: string;

  state: TorrentState;
  priority: TorrentPriority;

  progress: number;

  downloaded: number;
  uploaded: number;

  downloadSpeed: number;
  uploadSpeed: number;

  ratio: number;

  peers: number;
  seeds: number;

  timeRemaining: number;

  totalSize?: number;

  addedAt: number;
  startedAt?: number;
  completedAt?: number;
  updatedAt: number;

  lastProgressAt?: number;
  lastDownloadAt?: number;

  stalledSince?: number;

  retries: number;
  nextRetryAt?: number;

  limits: TorrentLimits;

  files?: TorrentFile[];

  error?: string;
}

export interface TorrentHistoryPoint {
  timestamp: number;

  downloadSpeed: number;
  uploadSpeed: number;

  downloaded: number;
  uploaded: number;

  peers: number;
  progress: number;
}
