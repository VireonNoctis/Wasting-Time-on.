import {
  torrentManager,
  torrentSseHeaders,
} from "@/lib/torrent-manager";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(
  request: Request,
) {
  await torrentManager.init();

  const encoder =
    new TextEncoder();

  const stream =
    new ReadableStream<Uint8Array>({
      start(controller) {
        let closed = false;

        const send = (
          event: string,
          data: unknown,
        ) => {
          if (closed) {
            return;
          }

          try {
            controller.enqueue(
              encoder.encode(
                `event: ${event}\n` +
                `data: ${JSON.stringify(data)}\n\n`,
              ),
            );
          } catch {
            cleanup();
          }
        };

        const onUpdate =
          (data: unknown) =>
            send("update", data);

        const onMetadata =
          (data: unknown) =>
            send("metadata", data);

        const onError =
          (data: unknown) =>
            send("error", data);

        const onNoPeers =
          (data: unknown) =>
            send("no-peers", data);

        const cleanup =
          () => {
            if (closed) {
              return;
            }

            closed = true;

            clearInterval(
              heartbeat,
            );

            torrentManager.off(
              "update",
              onUpdate,
            );

            torrentManager.off(
              "metadata",
              onMetadata,
            );

            torrentManager.off(
              "error",
              onError,
            );

            torrentManager.off(
              "no-peers",
              onNoPeers,
            );

            try {
              controller.close();
            } catch {
              // Already closed.
            }
          };

        const heartbeat =
          setInterval(
            () => {
              send(
                "ping",
                {
                  at: Date.now(),
                },
              );
            },
            15_000,
          );

        torrentManager.on(
          "update",
          onUpdate,
        );

        torrentManager.on(
          "metadata",
          onMetadata,
        );

        torrentManager.on(
          "error",
          onError,
        );

        torrentManager.on(
          "no-peers",
          onNoPeers,
        );

        send(
          "snapshot",
          torrentManager.list(),
        );

        request.signal.addEventListener(
          "abort",
          cleanup,
          {
            once: true,
          },
        );
      },
    });

  return new Response(
    stream,
    {
      headers:
        torrentSseHeaders(),
    },
  );
}
