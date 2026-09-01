import {
  NextResponse,
} from "next/server";

import {
  torrentManager,
} from "@/lib/torrent-manager";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  await torrentManager.init();

  const torrents =
    torrentManager.list();

  const active =
    torrents.filter(
      (torrent) =>
        torrent.state ===
          "downloading" ||
        torrent.state ===
          "seeding",
    );

  const downloading =
    torrents.filter(
      (torrent) =>
        torrent.state ===
        "downloading",
    );

  const seeding =
    torrents.filter(
      (torrent) =>
        torrent.state ===
        "seeding",
    );

  const stalled =
    torrents.filter(
      (torrent) =>
        torrent.state ===
        "stalled",
    );

  const totalDownloadSpeed =
    active.reduce(
      (total, torrent) =>
        total +
        torrent.downloadSpeed,
      0,
    );

  const totalUploadSpeed =
    active.reduce(
      (total, torrent) =>
        total +
        torrent.uploadSpeed,
      0,
    );

  const totalDownloaded =
    torrents.reduce(
      (total, torrent) =>
        total +
        torrent.downloaded,
      0,
    );

  const totalUploaded =
    torrents.reduce(
      (total, torrent) =>
        total +
        torrent.uploaded,
      0,
    );

  return NextResponse.json({
    status: "ok",

    torrents: {
      total: torrents.length,
      active: active.length,
      downloading:
        downloading.length,
      seeding:
        seeding.length,
      stalled:
        stalled.length,
    },

    bandwidth: {
      download:
        totalDownloadSpeed,
      upload:
        totalUploadSpeed,
    },

    totals: {
      downloaded:
        totalDownloaded,
      uploaded:
        totalUploaded,
    },

    uptime: process.uptime(),

    timestamp: Date.now(),
  });
}
