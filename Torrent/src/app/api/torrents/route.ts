import {
  NextRequest,
  NextResponse,
} from "next/server";

import {
  torrentManager,
} from "@/lib/torrent-manager";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  await torrentManager.init();

  return NextResponse.json({
    torrents: torrentManager.list(),
  });
}

export async function POST(
  request: NextRequest,
) {
  try {
    const body =
      await request.json() as {
        source?: unknown;
        path?: unknown;
      };

    if (
      typeof body.source !== "string" ||
      !body.source.trim()
    ) {
      return NextResponse.json(
        {
          error:
            "source must be a non-empty torrent source",
        },
        {
          status: 400,
        },
      );
    }

    const torrent =
      await torrentManager.add(
        body.source.trim(),
        {
          path:
            typeof body.path === "string"
              ? body.path
              : undefined,
        },
      );

    return NextResponse.json(
      torrent,
      {
        status: 201,
      },
    );
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : String(error),
      },
      {
        status: 500,
      },
    );
  }
}
