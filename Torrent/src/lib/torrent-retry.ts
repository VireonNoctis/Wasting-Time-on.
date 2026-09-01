// src/lib/torrent-retry.ts

export function retryDelay(
  attempt: number,
): number {
  const base = 2_000;

  const maximum =
    15 * 60 * 1000;

  const exponential =
    base *
    Math.pow(
      2,
      Math.max(
        0,
        attempt - 1,
      ),
    );

  const jitter =
    Math.floor(
      Math.random() * 2_000,
    );

  return Math.min(
    maximum,
    exponential + jitter,
  );
}
