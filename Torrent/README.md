Torrent Core (Written By Claude)

A high-end, server-side torrent management core designed to run alongside a Next.js application.

The goal of Torrent Core is to provide the torrent functionality behind a modern web interface without making the browser responsible for the heavy BitTorrent workload.

«Architecture note: Next.js is used as the application/API layer. The long-running torrent workload belongs to a Node.js torrent runtime, with persistent state and filesystem-backed storage.»

---

Table of Contents

1. "Overview" (#overview)
2. "Core Goals" (#core-goals)
3. "Architecture" (#architecture)
4. "Technology Stack" (#technology-stack)
5. "Torrent Lifecycle" (#torrent-lifecycle)
6. "Concurrent Torrents" (#concurrent-torrents)
7. "Downloading and Seeding" (#downloading-and-seeding)
8. "Magnet and Torrent Inputs" (#magnet-and-torrent-inputs)
9. "Large Torrents and 1 TB+ Data" (#large-torrents-and-1-tb-data)
10. "Queue and Scheduler" (#queue-and-scheduler)
11. "Priorities" (#priorities)
12. "Bandwidth Management" (#bandwidth-management)
13. "Pause and Resume" (#pause-and-resume)
14. "Persistent State" (#persistent-state)
15. "Automatic Recovery" (#automatic-recovery)
16. "Stall Detection" (#stall-detection)
17. "Retry Backoff" (#retry-backoff)
18. "File Management" (#file-management)
19. "File Selection" (#file-selection)
20. "Progress and Statistics" (#progress-and-statistics)
21. "Real-Time Events" (#real-time-events)
22. "Health Monitoring" (#health-monitoring)
23. "Graceful Shutdown" (#graceful-shutdown)
24. "Storage Safety" (#storage-safety)
25. "API" (#api)
26. "Example Requests" (#example-requests)
27. "Environment Variables" (#environment-variables)
28. "Production Deployment" (#production-deployment)
29. "Performance Considerations" (#performance-considerations)
30. "Failure Scenarios" (#failure-scenarios)
31. "Security Considerations" (#security-considerations)
32. "Recommended Directory Layout" (#recommended-directory-layout)
33. "Operational Checklist" (#operational-checklist)
34. "Completion Notes" (#completion-notes)

---

Overview

Lunar Torrent Core is the backend torrent subsystem for a Next.js application.

It is deliberately designed around a separation of responsibilities:

- Next.js handles HTTP APIs, authentication, dashboards, administration, and presentation.
- The Node.js torrent manager owns long-running torrent sessions.
- The torrent engine handles peer connections, pieces, trackers, DHT, PEX, seeding, verification, and transfer logic.
- The filesystem stores the actual torrent payload.
- Persistent metadata storage stores torrent state, configuration, progress information, retry state, and operational metadata.
- SSE/WebSocket-style event delivery exposes live torrent activity to the frontend.

This prevents a normal HTTP request from being responsible for a torrent that may remain active for hours or days.

---

Core Goals

The core is intended to cover the normal functionality expected from a serious torrent client/service:

- Multiple torrents at the same time.
- Downloading and seeding concurrently.
- Large multi-file torrents.
- 1 TB+ torrent payloads when the host storage and filesystem support them.
- Magnet links and torrent metadata.
- Persistent sessions.
- Pause/resume.
- Queueing.
- Priority scheduling.
- Per-torrent and global bandwidth limits.
- Automatic recovery.
- Stall detection.
- Retry with exponential backoff and jitter.
- File inspection and selection.
- Download/upload statistics.
- Historical throughput measurements.
- Live frontend updates.
- Health monitoring.
- Safe deletion boundaries.
- Graceful shutdown.

The torrent engine should remain independent from the visual Next.js interface so the engine can continue operating even when the dashboard is not open.

---

Architecture

                         ┌─────────────────────┐
                         │       Next.js       │
                         │ Dashboard / API / UI│
                         └──────────┬──────────┘
                                    │
                           HTTP / SSE / Auth
                                    │
                         ┌──────────▼──────────┐
                         │   Torrent Manager   │
                         │ Lifecycle / State   │
                         └──────────┬──────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
   ┌──────▼──────┐          ┌───────▼────────┐        ┌──────▼──────┐
   │  Scheduler  │          │   Bandwidth    │        │    Health   │
   │ Queue/Prior │          │    Manager     │        │   Monitor   │
   └──────┬──────┘          └───────┬────────┘        └──────┬──────┘
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    ▼
                           ┌──────────────────┐
                           │  Torrent Engine  │
                           │ Node-side client │
                           └────────┬─────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
           Torrent A            Torrent B           Torrent N
                │                   │                   │
                └───────────────────┼───────────────────┘
                                    ▼
                              Filesystem
                                    │
                              Metadata DB

The most important architectural rule is that the torrent client is a long-lived process/component, not something that is created on every API request.

---

Technology Stack

Recommended stack:

- Next.js for the application and API layer.
- Node.js runtime for server-side torrent control.
- WebTorrent in Node for the initial torrent implementation.
- SQLite or another persistent database for metadata and operational state.
- Filesystem storage for torrent payloads.
- Server-Sent Events (SSE) for lightweight live torrent updates.

For extremely high-throughput deployments, the torrent engine can later be replaced or moved to a dedicated native torrent service without changing the frontend contract significantly.

---

Torrent Lifecycle

A torrent normally moves through states similar to:

                ┌───────────┐
                │   queued  │
                └─────┬─────┘
                      │
                      ▼
              ┌───────────────┐
              │  downloading  │
              └───────┬───────┘
                      │
             100%     │
                      ▼
                ┌──────────┐
                │ seeding  │
                └────┬─────┘
                     │
                     ▼
                  paused /
                 stopped /
                 removed

Recovery paths can introduce:

          downloading
               │
               ▼
            stalled
               │
         retry/backoff
               │
               ▼
          downloading

Errors are tracked separately so the system can distinguish a transient network failure from a terminal failure.

---

Concurrent Torrents

The manager maintains multiple torrent sessions concurrently.

Example:

Torrent A   1.8 TB   ↓ 420 MB/s   ↑ 180 MB/s   47 peers
Torrent B   740 GB   ↓ 210 MB/s   ↑  90 MB/s   31 peers
Torrent C   3.2 TB   ↓   0 MB/s   ↑ 350 MB/s   92 peers
Torrent D   120 GB   ↓  80 MB/s   ↑  30 MB/s   18 peers

The exact number of simultaneous active torrents is controlled by the scheduler and host resources.

A queue prevents unlimited torrents from immediately becoming active when the configured concurrency limit is reached.

---

Downloading and Seeding

The same torrent session supports both downloading and seeding.

During downloading, the engine:

- discovers peers,
- requests pieces,
- verifies received data,
- writes verified pieces to storage,
- reports progress,
- and continues peer discovery while incomplete.

Once all pieces are present and verified, the torrent transitions to a seeding state.

Seeding can continue according to the configured policy, such as:

- upload-ratio target,
- minimum seed time,
- manual stop,
- or another configured rule.

A completed torrent is therefore not automatically treated as deleted data; it can remain available for upload to other peers.

---

Magnet and Torrent Inputs

The API accepts torrent sources as strings.

Typical inputs include:

- magnet URIs,
- ".torrent" file data handled by the application,
- torrent metadata supplied by an internal uploader/import layer.

For magnets, metadata may not be available immediately.

The torrent remains in a metadata-discovery phase until its metainfo is obtained.

Once metadata is available, the manager records:

- info hash,
- display name,
- total size,
- file list,
- and normal runtime statistics.

---

Large Torrents and 1 TB+ Data

1 TB+ torrents are technically compatible with BitTorrent-style piece transfer.

The actual practical limit is determined by the server rather than Next.js itself.

The major resource requirements are:

Storage capacity
Disk throughput
Filesystem limits
Network bandwidth
CPU used for verification
RAM used by the runtime
File descriptor limits
Peer connection count

For example, a host running several 1 TB torrents can require many terabytes of usable storage while also handling continuous disk I/O and network transfer.

The application must therefore avoid loading the complete torrent payload into memory.

Data is stored on disk and accessed in a streaming/fragmented manner by the torrent engine.

Recommended storage

For heavy workloads, prefer:

- NVMe SSD for metadata and active workloads where practical.
- Large HDD or RAID-backed storage for bulk payloads.
- A filesystem with strong support for large files.
- Adequate free space for incomplete torrents.
- Storage monitoring before starting large jobs.

A 1 TB torrent should never be treated as a 1 TB RAM workload. Only the required active data and metadata should be resident in memory.

---

Queue and Scheduler

When the number of requested torrents exceeds the configured active limit, additional torrents enter a queue.

Example:

MAX_ACTIVE = 4

Torrent A → downloading
Torrent B → downloading
Torrent C → seeding
Torrent D → downloading

Torrent E → queued
Torrent F → queued
Torrent G → queued

When an active slot becomes available, the scheduler selects the next eligible torrent.

Queue decisions can take:

- priority,
- original insertion time,
- retry time,
- manually requested start state,
- and configured policies

into account.

This is preferable to starting every torrent immediately.

---

Priorities

Each torrent can have a priority such as:

low
normal
high
critical

Suggested ordering:

critical > high > normal > low

Within the same priority, FIFO ordering can be used as a predictable fallback.

Example:

Critical Torrent
High Torrent
High Torrent
Normal Torrent
Normal Torrent
Low Torrent

This allows important downloads to move through the queue without manually rearranging every item.

---

Bandwidth Management

Bandwidth can be controlled globally and per torrent.

Example:

Global download limit: 500 MB/s
Global upload limit:   200 MB/s

Individual torrents can then override their own limits:

Torrent A → unlimited within global allocation
Torrent B → 50 MB/s
Torrent C → 10 MB/s

A scheduler/bandwidth layer should avoid blindly allowing every torrent to consume the entire network pipe.

This becomes increasingly important as concurrency grows.

---

Pause and Resume

Pause stops active transfer without deleting torrent state or payload data.

Example:

POST /api/torrents/<id>/pause

Resume reactivates the existing torrent session.

POST /api/torrents/<id>/resume

The important behavior is that a pause does not imply deletion.

Already-downloaded data remains intact.

---

Persistent State

Torrent state must survive application restarts.

Persistent information includes:

torrent ID
source
info hash
name
storage path
state
priority
progress
downloaded bytes
uploaded bytes
ratio
total size
timestamps
retry count
retry state
bandwidth limits
errors

For a prototype, JSON persistence is acceptable.

For a production deployment, SQLite or another transactional database is preferable.

Why SQLite

SQLite avoids repeatedly rewriting an ever-growing JSON file and provides:

- atomic updates,
- indexing,
- concurrent reads,
- structured queries,
- history tables,
- easier migrations,
- recovery semantics.

The payload files remain on the filesystem; only metadata needs to live in the database.

---

Automatic Recovery

The system should recover torrents where possible rather than permanently failing on temporary network problems.

Example:

downloading
     ↓
network failure
     ↓
error/stalled
     ↓
retry
     ↓
downloading

Recovery should be bounded.

A torrent that continually fails must eventually become a terminal error instead of retrying forever.

---

Stall Detection

A torrent can technically remain "active" while making no useful progress.

The health monitor tracks:

- last measurable progress,
- current peer count,
- current transfer rate,
- current state,
- elapsed idle time.

Example:

No peers + no progress
        ↓
     stalled

No progress for extended period
        ↓
     stalled

A stalled torrent can then be retried according to the configured policy.

---

Retry Backoff

Retries should use exponential backoff.

Example:

Attempt 1 → ~2 seconds
Attempt 2 → ~4 seconds
Attempt 3 → ~8 seconds
Attempt 4 → ~16 seconds
...

A maximum retry interval prevents the delay from becoming unreasonably large.

Random jitter should also be applied so a large number of failed torrents do not all reconnect at exactly the same moment.

---

File Management

Multi-file torrents expose each individual payload file.

A file record can contain:

{
  "index": 0,
  "path": "Example/Video.mkv",
  "name": "Video.mkv",
  "length": 894734123421,
  "progress": 0.73,
  "selected": true
}

This makes the system capable of presenting file-level information to the frontend rather than only aggregate torrent progress.

---

File Selection

For multi-file torrents, file selection can be supported so users can avoid downloading unnecessary files.

Example:

Torrent
├── video.mkv       selected
├── subtitles.zip   selected
├── extras.zip      deselected
└── sample.mkv      deselected

This is especially useful for large collections.

The torrent engine remains responsible for piece-level integrity while the manager handles which files are selected.

---

Progress and Statistics

A torrent record can expose:

progress
downloaded
uploaded
download speed
upload speed
ratio
peer count
seed count
ETA
total size

Example:

{
  "progress": 0.742,
  "downloaded": 812374923842,
  "uploaded": 124923742821,
  "downloadSpeed": 184392124,
  "uploadSpeed": 23948231,
  "ratio": 0.153,
  "peers": 47,
  "timeRemaining": 3824
}

The frontend should not need to calculate these values itself.

---

Historical Throughput

Instantaneous speed is useful but can fluctuate heavily.

The manager can periodically sample:

timestamp
download speed
upload speed
downloaded
uploaded
peer count
progress

This can then be used to generate:

- speed graphs,
- average speed,
- peak speed,
- throughput history,
- transfer summaries.

A rolling history should be bounded so memory usage doesn't grow indefinitely.

---

Real-Time Events

The API can expose Server-Sent Events so a dashboard can receive live changes.

Example:

GET /api/torrents/events

Events can include:

snapshot
metadata
update
error
no-peers
stalled
ping

Example event:

event: update
data: {
  "id": "abc123",
  "progress": 0.842,
  "downloadSpeed": 182392123,
  "uploadSpeed": 28329123,
  "peers": 51
}

This is considerably more efficient than continuously polling every torrent.

---

Health Monitoring

A global health endpoint can expose service-wide statistics.

Example:

GET /api/torrents/health

Possible response:

{
  "status": "ok",
  "torrents": {
    "total": 12,
    "active": 8,
    "downloading": 5,
    "seeding": 3,
    "stalled": 1
  },
  "bandwidth": {
    "download": 483921233,
    "upload": 120392821
  },
  "totals": {
    "downloaded": 9138492128374,
    "uploaded": 2938492837423
  },
  "uptime": 82931,
  "timestamp": 1760000000000
}

This endpoint can be used by an external monitoring system as well as the application dashboard.

---

Graceful Shutdown

Torrenting is long-running work, so shutdown behavior matters.

When the Node process receives a termination signal:

SIGTERM / SIGINT
       ↓
Stop accepting new work
       ↓
Persist torrent state
       ↓
Flush important metadata
       ↓
Destroy torrent sessions cleanly
       ↓
Exit

The next startup can then restore eligible torrents.

A process should not simply terminate in the middle of persistence and assume everything will be reconstructed perfectly.

---

Storage Safety

Destructive filesystem operations need strict path validation.

The manager must never blindly accept an arbitrary path supplied by an HTTP client and recursively delete it.

Recommended rules:

- all torrent payload paths live beneath an approved storage root,
- deletion is restricted to that root,
- parent directory traversal is rejected,
- symlink handling should be considered,
- free-space checks should run before beginning large jobs,
- storage quotas should be enforced where appropriate.

---

API

Core API:

GET    /api/torrents
POST   /api/torrents

GET    /api/torrents/:id
DELETE /api/torrents/:id

POST   /api/torrents/:id/pause
POST   /api/torrents/:id/resume

GET    /api/torrents/events
GET    /api/torrents/health

Additional production routes can include:

GET  /api/torrents/:id/files
POST /api/torrents/:id/files/select
POST /api/torrents/:id/files/deselect

POST /api/torrents/:id/priority
POST /api/torrents/:id/limits

POST /api/torrents/:id/recheck
POST /api/torrents/:id/retry

GET  /api/torrents/:id/history

GET  /api/settings
POST /api/settings

---

Example Requests

Add torrent

POST /api/torrents
Content-Type: application/json

{
  "source": "magnet:?xt=urn:btih:...",
  "path": "/storage/torrents/example"
}

Pause

POST /api/torrents/abc123/pause

Resume

POST /api/torrents/abc123/resume

Delete torrent but retain data

DELETE /api/torrents/abc123

Delete torrent and its payload

DELETE /api/torrents/abc123?deleteData=true

The application layer should authenticate and authorize all such operations before forwarding them to the manager.

---

Environment Variables

Suggested configuration:

TORRENT_DATA_DIR=/storage/torrents
TORRENT_MAX_ACTIVE=8
TORRENT_MAX_RETRIES=8
TORRENT_STALLED_AFTER=300000
TORRENT_HEALTH_INTERVAL=10000
TORRENT_STATS_INTERVAL=2000
TORRENT_PERSIST_INTERVAL=750
TORRENT_DOWNLOAD_LIMIT=0
TORRENT_UPLOAD_LIMIT=0
TORRENT_AUTO_RESUME=true
TORRENT_DHT=true
TORRENT_LSD=true
TORRENT_UPNP=false

Meaning

"TORRENT_DATA_DIR"
Root directory used for torrent payload and runtime data.

"TORRENT_MAX_ACTIVE"
Maximum number of active torrent sessions before new torrents enter the queue.

"TORRENT_MAX_RETRIES"
Maximum number of automatic recovery attempts.

"TORRENT_STALLED_AFTER"
Duration before a torrent can be considered stalled.

"TORRENT_HEALTH_INTERVAL"
How often the health monitor evaluates torrents.

"TORRENT_STATS_INTERVAL"
How often historical statistics are sampled.

"TORRENT_PERSIST_INTERVAL"
Minimum persistence delay used to avoid writing state excessively.

"TORRENT_DOWNLOAD_LIMIT"
Global download limit in bytes per second. "0" = unlimited.

"TORRENT_UPLOAD_LIMIT"
Global upload limit in bytes per second. "0" = unlimited.

"TORRENT_AUTO_RESUME"
Whether normal torrents are reconstructed automatically after restart.

"TORRENT_DHT"
Enable DHT peer discovery.

"TORRENT_LSD"
Enable local peer discovery.

"TORRENT_UPNP"
Enable automatic router port mapping where supported and desired.

---

Production Deployment

For a real deployment, do not assume that a regular serverless Next.js runtime is suitable for persistent torrent sessions.

Use a persistent Node process or dedicated worker service.

Recommended deployment model:

                         Reverse Proxy
                              │
                    ┌─────────▼─────────┐
                    │      Next.js      │
                    │ Dashboard / API   │
                    └─────────┬─────────┘
                              │
                       Internal API
                              │
                    ┌─────────▼─────────┐
                    │ Torrent Worker    │
                    │ Long-lived Node   │
                    └─────────┬─────────┘
                              │
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
              Torrent A   Torrent B   Torrent N
                  │           │           │
                  └───────────┼───────────┘
                              ▼
                         Torrent Storage

For larger environments, the worker can be separated completely from the Next.js machine.

That allows the web application and torrent workload to scale independently.

---

Performance Considerations

The highest throughput bottleneck is usually not Next.js.

The important bottlenecks are:

Disk

Large torrents can generate substantial random and sequential I/O.

Network

A server capable of hundreds of megabytes per second of transfer needs a network path that can actually sustain that rate.

CPU

Piece verification and protocol work consume CPU, particularly with many simultaneous peers.

Peer count

Thousands of peer connections increase memory, CPU, socket, and file descriptor usage.

File descriptors

Linux limits may need adjustment for high peer/torrent counts.

Storage capacity

A torrent containing 1 TB of content needs approximately 1 TB of usable storage, plus headroom for other torrents, metadata, temporary space, and filesystem overhead.

Persistence frequency

Statistics can change many times per second. Writing every event synchronously to a database is wasteful. Sampling and debouncing should be used instead.

---

Failure Scenarios

Process restart

Persisted torrent metadata is reloaded and eligible torrents are reconstructed.

Network interruption

The torrent remains known to the system and can reconnect once network connectivity returns.

Tracker outage

DHT, PEX, other configured discovery mechanisms, and later tracker retries can continue peer discovery when available.

Torrent with no peers

The torrent remains stalled/idle according to configured policy and can be retried rather than consuming resources forever.

Disk full

The service should detect insufficient space and transition the affected torrent into an error state rather than blindly continuing writes.

Corrupted piece

The torrent engine should reject invalid data through its normal piece verification process and request valid data again.

Corrupt metadata database

A production deployment should use database backups and recovery procedures.

Payload data should not depend on a single fragile metadata file.

---

Security Considerations

Torrent functionality is powerful and should not be exposed as an unauthenticated public API.

Recommended controls include:

- authenticate administrative endpoints,
- authorize torrent creation/removal,
- validate all input sources,
- restrict writable storage paths,
- prevent arbitrary filesystem deletion,
- enforce disk quotas,
- enforce bandwidth quotas where appropriate,
- rate-limit API calls,
- sanitize torrent/file metadata before rendering it in HTML,
- isolate the torrent worker from unrelated sensitive filesystem locations.

The Next.js layer should not accept an arbitrary filesystem path and directly pass it into a destructive operation.

---

Recommended Directory Layout

lunar-torrent-core/
│
├── src/
│   ├── app/
│   │   └── api/
│   │       └── torrents/
│   │           ├── route.ts
│   │           ├── health/
│   │           │   └── route.ts
│   │           ├── events/
│   │           │   └── route.ts
│   │           └── [id]/
│   │               ├── route.ts
│   │               ├── pause/
│   │               │   └── route.ts
│   │               └── resume/
│   │                   └── route.ts
│   │
│   └── lib/
│       ├── torrent-manager.ts
│       ├── torrent-types.ts
│       ├── torrent-config.ts
│       ├── torrent-scheduler.ts
│       ├── torrent-health.ts
│       ├── torrent-retry.ts
│       ├── torrent-files.ts
│       ├── torrent-history.ts
│       └── bandwidth-manager.ts
│
├── data/
│   └── torrents/
│
├── package.json
└── README.md

The exact filenames can be reorganized without changing the architecture.

---

Operational Checklist

Before putting the service into real use, verify:

- [ ] Persistent Node runtime is used.
- [ ] Torrent storage is on a filesystem designed for large payloads.
- [ ] Sufficient free disk space exists.
- [ ] File descriptor limits are appropriate.
- [ ] Upload/download bandwidth limits are configured.
- [ ] Active torrent concurrency is configured.
- [ ] Authentication protects management endpoints.
- [ ] Destructive filesystem actions are path-restricted.
- [ ] Database/state backups exist.
- [ ] Graceful shutdown is enabled.
- [ ] Health monitoring is enabled.
- [ ] Retry limits are configured.
- [ ] Stalled torrent handling is enabled.
- [ ] The torrent worker is monitored as a long-running process.
- [ ] Logs and metrics are collected.

---

Completion Notes

The completed design intentionally keeps the system separated into distinct responsibilities:

API
 ↓
Manager
 ↓
Scheduler + Bandwidth + Health + Persistence
 ↓
Torrent Engine
 ↓
Filesystem + Database

That separation is what makes the system scalable and maintainable.

The system is capable of managing multiple simultaneous torrents, normal downloading and seeding behavior, large torrent payloads, persistent state, queueing, priorities, bandwidth management, file-level control, live statistics, health monitoring, and automatic recovery.

Important practical limit

A statement such as "supports 1 TB+ torrents" means the software architecture does not impose a 1 TB application-level ceiling.

It does not mean that any machine can transfer a 1 TB torrent efficiently.

Actual throughput and concurrency remain bounded by:

network capacity
storage capacity
storage throughput
CPU
RAM
peer count
filesystem limits
operating-system limits

Next.js role

Next.js remains the interface and control plane.

Long-running torrent sessions should stay in a persistent Node process/worker and should not depend on a browser tab remaining open.

Final architecture

┌──────────────────────────────────────────────────────────┐
│                     Lunar Application                    │
│                                                          │
│  Next.js UI ── API ── Auth ── SSE / Live Statistics     │
│                         │                                │
│                         ▼                                │
│                 Torrent Controller                       │
│                         │                                │
│       ┌─────────────────┼─────────────────┐              │
│       ▼                 ▼                 ▼              │
│   Scheduler       Bandwidth Manager   Health Monitor    │
│       │                 │                 │              │
│       └─────────────────┼─────────────────┘              │
│                         ▼                                │
│                   Torrent Engine                         │
│                         │                                │
│          ┌──────────────┼──────────────┐                 │
│          ▼              ▼              ▼                 │
│       Torrent A      Torrent B      Torrent N            │
│          │              │              │                 │
│          └──────────────┼──────────────┘                 │
│                         ▼                                │
│                     Storage                              │
│                         │                                │
│                      SQLite                              │
└──────────────────────────────────────────────────────────┘

