import type {
  TorrentRecord,
} from "./torrent-types";

import type {
  SeedingPolicy,
  SeedingRuntime,
  SeedStopReason,
} from "./seeding-types";

export interface SeedDecision {
  action:
    | "continue"
    | "start"
    | "stop"
    | "wait";

  reason?: SeedStopReason | "not-scheduled";
}

function ratioReached(
  torrent: TorrentRecord,
  policy: SeedingPolicy,
): boolean {
  if (
    policy.targetRatio === undefined
  ) {
    return false;
  }

  if (
    torrent.downloaded <= 0
  ) {
    return false;
  }

  return (
    torrent.ratio >=
    policy.targetRatio
  );
}

function timeReached(
  runtime: SeedingRuntime,
  policy: SeedingPolicy,
): boolean {
  if (
    policy.maxSeedTime === undefined
  ) {
    return false;
  }

  return (
    runtime.totalSeedTime >=
    policy.maxSeedTime
  );
}

function minimumTimeReached(
  runtime: SeedingRuntime,
  policy: SeedingPolicy,
): boolean {
  if (
    policy.minSeedTime === undefined
  ) {
    return true;
  }

  return (
    runtime.totalSeedTime >=
    policy.minSeedTime
  );
}

function peerLimitReached(
  torrent: TorrentRecord,
  policy: SeedingPolicy,
  runtime: SeedingRuntime,
): boolean {
  if (
    policy.maxPeers === undefined
  ) {
    return false;
  }

  if (
    torrent.peers <=
    policy.maxPeers
  ) {
    runtime.consecutiveHighPeerChecks = 0;
    return false;
  }

  runtime.consecutiveHighPeerChecks += 1;

  return (
    runtime.consecutiveHighPeerChecks >= 3
  );
}

function idleReached(
  torrent: TorrentRecord,
  policy: SeedingPolicy,
  runtime: SeedingRuntime,
  now: number,
): boolean {
  if (
    policy.idleTimeout === undefined
  ) {
    return false;
  }

  if (
    torrent.peers > 0
  ) {
    runtime.lastPeerAt = now;
    return false;
  }

  const reference =
    runtime.lastPeerAt ??
    runtime.startedAt ??
    now;

  return (
    now - reference >=
    policy.idleTimeout
  );
}

function scheduleActive(
  policy: SeedingPolicy,
  now = new Date(),
): boolean {
  if (
    !policy.schedule
  ) {
    return true;
  }

  const schedule =
    policy.schedule;

  const day =
    now.getDay();

  if (
    !schedule.days.includes(day)
  ) {
    return false;
  }

  const minutes =
    now.getHours() * 60 +
    now.getMinutes();

  const start =
    schedule.startHour * 60 +
    schedule.startMinute;

  const end =
    schedule.endHour * 60 +
    schedule.endMinute;

  // Same-day schedule.
  if (start <= end) {
    return (
      minutes >= start &&
      minutes < end
    );
  }

  // Overnight schedule.
  return (
    minutes >= start ||
    minutes < end
  );
}

export function evaluateSeeding(
  torrent: TorrentRecord,
  policy: SeedingPolicy,
  runtime: SeedingRuntime,
  now = Date.now(),
): SeedDecision {
  if (!policy.enabled) {
    return {
      action: "stop",
      reason: "disabled",
    };
  }

  if (
    policy.forceSeed ||
    policy.pinned
  ) {
    return {
      action:
        torrent.state === "seeding"
          ? "continue"
          : "start",
    };
  }

  if (
    !scheduleActive(
      policy,
      new Date(now),
    )
  ) {
    return {
      action: "wait",
      reason: "not-scheduled",
    };
  }

  const minimumSatisfied =
    minimumTimeReached(
      runtime,
      policy,
    );

  if (
    !minimumSatisfied
  ) {
    return {
      action:
        torrent.state === "seeding"
          ? "continue"
          : "start",
    };
  }

  const ratio =
    ratioReached(
      torrent,
      policy,
    );

  const time =
    timeReached(
      runtime,
      policy,
    );

  const peers =
    peerLimitReached(
      torrent,
      policy,
      runtime,
    );

  const idle =
    idleReached(
      torrent,
      policy,
      runtime,
      now,
    );

  switch (policy.mode) {
    case "always":
      return {
        action:
          torrent.state === "seeding"
            ? "continue"
            : "start",
      };

    case "ratio":
      return ratio
        ? {
            action: "stop",
            reason: "ratio-reached",
          }
        : {
            action:
              torrent.state === "seeding"
                ? "continue"
                : "start",
          };

    case "time":
      return time
        ? {
            action: "stop",
            reason: "time-reached",
          }
        : {
            action:
              torrent.state === "seeding"
                ? "continue"
                : "start",
          };

    case "ratio-or-time":
      if (ratio) {
        return {
          action: "stop",
          reason: "ratio-reached",
        };
      }

      if (time) {
        return {
          action: "stop",
          reason: "time-reached",
        };
      }

      return {
        action:
          torrent.state === "seeding"
            ? "continue"
            : "start",
      };

    case "ratio-and-time":
      if (ratio && time) {
        return {
          action: "stop",
          reason: "ratio-reached",
        };
      }

      return {
        action:
          torrent.state === "seeding"
            ? "continue"
            : "start",
      };

    case "peers":
      if (peers) {
        return {
          action: "stop",
          reason: "peer-limit",
        };
      }

      if (idle) {
        return {
          action: "stop",
          reason: "idle-timeout",
        };
      }

      return {
        action:
          torrent.state === "seeding"
            ? "continue"
            : "start",
      };

    case "until-disabled":
      return {
        action:
          torrent.state === "seeding"
            ? "continue"
            : "start",
      };

    case "scheduled":
      if (idle) {
        return {
          action: "wait",
          reason: "not-scheduled",
        };
      }

      return {
        action:
          torrent.state === "seeding"
            ? "continue"
            : "start",
      };

    default:
      return {
        action:
          torrent.state === "seeding"
            ? "continue"
            : "start",
      };
  }
}
