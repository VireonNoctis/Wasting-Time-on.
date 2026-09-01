import {
  NextRequest,
  NextResponse,
} from "next/server";

import {
  torrentManager,
} from "@/lib/torrent-manager";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  {
    params,
  }: {
    params: Promise<{
      id: string;
    }>;
  },
) {
  await torrentManager.init();

  const { id } = await params;

  const torrent =
    torrentManager.get(id);

  if (!torrent) {
    return NextResponse.json(
      {
        error: "Torrent not found",
      },
      {
        status: 404,
      },
    );
  }

  return NextResponse.json(
    torrent,
  );
}

export async function DELETE(
  request: NextRequest,
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

    const deleteData =
      request.nextUrl.searchParams.get(
        "deleteData",
      ) === "true";

    await torrentManager.remove(
      id,
      deleteData,
    );

    return new NextResponse(
      null,
      {
        status: 204,
      },
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
