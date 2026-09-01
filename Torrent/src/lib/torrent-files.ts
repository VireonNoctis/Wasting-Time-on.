// src/lib/torrent-files.ts

import type {
  TorrentFile,
} from "./torrent-types";

export function inspectFiles(
  torrent: any,
): TorrentFile[] {
  if (
    !torrent?.files
  ) {
    return [];
  }

  return torrent.files.map(
    (
      file: any,
      index: number,
    ) => ({
      index,

      path:
        typeof file.path === "string"
          ? file.path
          : "",

      name:
        typeof file.name === "string"
          ? file.name
          : "",

      length:
        Number.isFinite(
          file.length,
        )
          ? file.length
          : 0,

      progress:
        Number.isFinite(
          file.progress,
        )
          ? file.progress
          : 0,

      selected:
        !file.deselect,
    }),
  );
}
