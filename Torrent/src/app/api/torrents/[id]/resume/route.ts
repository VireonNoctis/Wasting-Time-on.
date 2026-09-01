import {
  NextResponse,
} from "next/server";

import {
  torrentManager,
} from "@/lib/torrent-manager";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  _request: Request,
  {
    params,
  }: {
    params: Promise<{
      id: string;
    }>;
  },
) {
  try {
    const { id } = await params;

    return NextResponse.json(
      await torrentManager.resume(id),
    );
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : String(error);

    return NextResponse.json(
      {
        error: message,
      },
      {
        status:
          message.includes(
            "was not found",
          )
            ? 404
            : 500,
      },
    );
  }
}
