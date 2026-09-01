import path from "node:path";

function numberEnv(
  name: string,
  fallback: number,
): number {
  const value = Number(
    process.env[name],
  );

  return Number.isFinite(value)
    ? value
    : fallback;
}

function booleanEnv(
  name: string,
  fallback: boolean,
): boolean {
  const value =
    process.env[name];

  if (value === undefined) {
    return fallback;
  }

  return value === "true";
}

export const torrentConfig = {
  dataDirectory:
    process.env.TORRENT_DATA_DIR ||
    path.resolve(
      process.cwd(),
      "data/torrents",
    ),

  maxActive:
    numberEnv(
      "TORRENT_MAX_ACTIVE",
      8,
    ),

  maxRetries:
    numberEnv(
      "TORRENT_MAX_RETRIES",
      8,
    ),

  stalledAfter:
    numberEnv(
      "TORRENT_STALLED_AFTER",
      5 * 60 * 1000,
    ),

  healthInterval:
    numberEnv(
      "TORRENT_HEALTH_INTERVAL",
      10_000,
    ),

  statisticsInterval:
    numberEnv(
      "TORRENT_STATS_INTERVAL",
      2_000,
    ),

  persistenceInterval:
    numberEnv(
      "TORRENT_PERSIST_INTERVAL",
      750,
    ),

  defaultDownloadLimit:
    numberEnv(
      "TORRENT_DOWNLOAD_LIMIT",
      0,
    ),

  defaultUploadLimit:
    numberEnv(
      "TORRENT_UPLOAD_LIMIT",
      0,
    ),

  autoResume:
    booleanEnv(
      "TORRENT_AUTO_RESUME",
      true,
    ),

  enableDht:
    booleanEnv(
      "TORRENT_DHT",
      true,
    ),

  enableLsd:
    booleanEnv(
      "TORRENT_LSD",
      true,
    ),

  enableUpnp:
    booleanEnv(
      "TORRENT_UPNP",
      false,
    ),
} as const;
