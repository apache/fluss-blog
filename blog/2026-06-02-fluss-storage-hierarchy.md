---
slug: fluss-storage-hierarchy
title: "The Storage Hierarchy: Hot, Remote, and Lake"
date: 2026-06-02
authors: [giannis]
image: ./assets/column_pruning/banner.png
---

![Banner](assets/storage_hierarchy/banner.png)

## Three-Tier Storage Hierarchy
Fluss organizes its storage into three tiers. Each tier has a different latency profile,
a different data format, and different rules governing when data can be deleted.
Understanding which tier holds which data at any moment is the foundation for
things like capacity planning, latency expectations, correct read-path design, and disaster recovery all depend on it.
<!-- truncate -->

The first tier is **local disk on the tablet server**. It holds the hot data: recent log
segments, the full live RocksDB KV state for every primary key table, and a local
view of the most recent KV snapshots (which exist as hard links to live SST files
while uploads are in flight). Reads from this tier are microseconds to milliseconds.

The second tier is **remote object storage** (like S3), used for two distinct
purposes that share the same `remote.data.dir` filesystem: (a) older log segments
uploaded by the remote-log tiering task in Fluss's native binary format, extending
local retention without growing local disk, and (b) durable KV snapshots for every
primary key table, uploaded periodically so that a tablet server can recover after
disk loss. Remote log storage is **enabled by default**: it is controlled by
`remote.log.task-interval-duration (default 1min)`, and is disabled only when that
value is `set to 0`. KV snapshot
upload is independent of remote-log tiering and is governed by
`kv.snapshot.interval (default 10min)` .

The third tier is **the lakehouse** (Paimon, Iceberg, Hudi (WIP), or Lance), holding
data in analytical file formats queryable by any engine. Reads from the lakehouse
take seconds. **The lakehouse is never on the Fluss server's read or recovery path.**

> **On single-copy storage.** Apache Fluss is single-copy in steady state: hot data on the
server, cold data in the lakehouse, no permanent duplication.
> **The one exception:**
when lakehouse tiering is enabled, a remote log segment is only deleted once **both**
its TTL has expired **and** the lakehouse has ingested it, a safety net against
lakehouse lag. This creates a bounded window where the same data lives in both
Tier 2 and Tier 3, governed by `table.log.ttl` (default 7 days). Shorten it if strict
single-copy matters more than a long catch-up window. The overlap is a configurable,
time-bounded transition, **not another copy**.

![](assets/storage_hierarchy/fig1.png)

## Log Table Data Lifecycle

A log table's data on local disk is organized as log segments. 
Pairs of a `.log file` (raw records) and an `.index file` (offset index for fast seek). 
The active segment is open for appends; all others are immutable and named by their starting offset. 
What happens to these segments after they are written is governed by a single retention TTL (`table.log.ttl, default 7 days`) that defines the lifetime of log data in the table, plus, when remote tiering is enabled 
and a count-based local-side override (`table.log.tiered.local-segments, default 2`) that keeps a minimum hot window on local disk regardless of TTL.

![](assets/storage_hierarchy/fig2.png)

A segment becomes a candidate for upload to remote storage **only after it is sealed**.
Once Fluss closes it and stops accepting writes into it. 
The active segment, by definition, is still open, so the tiering task will not touch it. 
When the active segment hits its size threshold it rolls over: Fluss seals the current active segment (which becomes immutable) and opens a new active segment for subsequent writes. 
The freshly-sealed one is now a candidate the tiering task can pick up on its next round. 
This is the same model Kafka uses for its tiered storage. 

**The end result:** **data sitting in the active segment lives only on the local Fluss server until rollover**, which is why the active segment's size threshold acts as a lower bound on how recent your "remote-only" reads can be.

### Two paths, one critical difference
By default, remote log storage is active `(remote.log.task-interval-duration=1 min)` and the per-table TTL `(table.log.ttl)` defaults to 7 days. 
The TTL is the global retention contract for the log and it defines the maximum age of log data in the table, regardless of which physical tier it lives on. 
When remote tiering is enabled, the remote-log task implements that contract: it uploads sealed segments to S3, trims local segments down to `table.log.tiered.local-segments` (default: 2) once they have been uploaded, and expires S3 segments past TTL. 
In this configuration the local-disk footprint is bounded primarily by the count-based keep-N floor (typically a small hot window of recent segments), and the TTL value applies most visibly on the S3 side because that is where data lives longest.

If you set `remote.log.task-interval-duration=0`, you opt out of Tier 2 entirely and you also opt out of the scheduled cleanup task itself, because that task is what runs both upload and segment deletion. 
In this mode there is no scheduled component trimming local segments. 
This is Path A, and **the practical failure mode is unbounded local-disk growth**: eventually the tablet server runs out of disk and write batches start failing with storage exceptions.
**There is no automatic fallback to the lakehouse on the write path.**
Running Fluss with the scheduled task disabled is meant for narrow scenarios, it is not the supported steady-state mode, which is why remote log storage ships enabled by default.

![](assets/storage_hierarchy/fig3.png)

## Remote Log Storage vs. Lakehouse Tiering
These two features are independent and are frequently conflated. Each solves a different problem and has a completely different output format.

**Remote log storage** is about disk economics on the tablet server. It copies raw log segments in Fluss's native binary format to S3, extending local retention without growing local disk. The tablet server can read from S3 when a consumer requests an offset that has been trimmed locally. It is managed entirely server-side by a background task. As a side effect it is also **the only mechanism that trims local log segments**.

**Lakehouse tiering** is about analytical access. It converts Fluss data into lakehouse-native formats (ORC, Parquet, Lance) and writes them to the lakehouse via an external Flink job (the Tiering Service). The output is queryable by Spark, Trino, and Flink independently of Fluss.

These are complementary layers, and you can run any combination of them. When both are enabled, the lakehouse confirmation acts as an additional safety gate on top of the TTL-based S3 deletion.

### Freshness is a cadence, not a guarantee
`table.datalake.freshness` (default 3 minutes) is the **cadence** at which tiering
rounds are initiated. **It is not a bound on how stale a lakehouse query result will
be at the moment you run it.** Inside each round, the tiering service freezes the
current Fluss log end offset as the stopping offset at split-generation time;
anything written after that point flows into the next round. Under moderate write
rates, expect observed staleness in the 3–6 minute range, with spikes during heavy
bursts. If you need sub-minute freshness, route through the Fluss-aware connector
path · the lakehouse on its own is fresh enough for analytics, not for live decisioning.

## Primary Key Table Data Lifecycle
A log table has one thing on disk, the log. A primary key table has three. They serve different roles, they live in different places, and they fail in different ways. Operating PK tables without seeing them as three distinct structures is one of the faster routes to a confusing production incident.
![](assets/storage_hierarchy/fig4.png)

### Structure 1: Live RocksDB

This is the current state of the table. One entry per primary key, always up to date, sitting on the tablet server's local disk in a RocksDB instance. Every point lookup reads from here. Every upsert merges into here. It is created when the tablet opens and deleted only when the table is dropped. Nothing moves it and there is no setting that puts the live state on S3, in the lakehouse, or anywhere else. **RocksDB on local disk is where the work happens, and that's the only place it can happen.**

The trap is assuming this is also where your data is durably stored. It is not. **The live store is what serves traffic; what survives a disk loss is the snapshot in remote storage (Structure 2).** Two different roles, two different copies, related data.

You need local disk for the full merged state of every bucket the tablet server is responsible for. **The lakehouse cannot stand in for this** and the tablet server doesn't read PK state from the lake under any circumstances.

### Structure 2: KV Snapshots

Every ten minutes by default, the tablet server takes a snapshot of the live RocksDB, which is a point-in-time copy that ends up in remote storage. **This is the system's only durable record of the table's current state.** If the tablet server's local disk evaporates, the most recent snapshot is what brings the data back.

It helps to understand how a snapshot is actually built, because the mechanics are not where most people guess they are.

Step one happens locally and completes immediately. The tablet server makes hard-link references to the current RocksDB data files into a staging directory. **No bytes get copied · just new pointers to existing files.** This is what lets a snapshot start instantly regardless of how large the table is, because nothing is being duplicated on disk. Step two is the one that actually moves data. Those files plus a bit of metadata get uploaded to remote storage. The remote copy is the durable one; the local staging directory is just there so the uploader sees a frozen, consistent view of the files while RocksDB keeps writing and compacting underneath it. The snapshot is considered durable once the upload finishes.

Fluss keeps the last two snapshots in remote storage by default. When a new snapshot supersedes an old one, the old one is deleted, with one important guard. If anything (most commonly a long-running lakehouse tiering job) is still reading an older snapshot, a lease prevents the cleanup from removing it underneath the reader. This sounds like a detail, but it becomes load-bearing the first time a large primary key table takes longer to tier than the gap between snapshots and the lease is what keeps the system from racing itself.

### Structure 3: Changelog Log

Every upsert and every delete also gets appended to a log, in the order it happened. This log behaves exactly like a regular log table on disk · same retention rules, same tiering to remote storage, same handoff to the lakehouse.

Two things make the changelog different from the rest of the table.

**It grows with the number of writes, not with the number of unique keys.** A primary key table that updates the same 100 keys ten million times has a small live store and an enormous changelog. RocksDB collapses by key; the log does not. This is what makes the changelog useful as a CDC feed and downstream consumers see every change in order, not just the latest value.

**Deleting old changelog segments has no effect on the live store.** The live store is complete on its own; it doesn't need the log to know the current value of any key. The log is there for replay (when a tablet needs to recover) and for downstream feed (when something is reading change events). It is not a place where state lives.

![](assets/storage_hierarchy/fig5.png)


### Recovery: Independent Tracks, Coupled Outcomes

The snapshot uploads and the log uploads look independent from a configuration standpoint · separate settings, separate schedulers, separate places in remote storage. **They are not independent when you actually need to recover from disk loss.**

Recovery on a fresh tablet server works in two stages. The snapshot brings the live state up to whatever point it was taken at. The changelog then replays every change since that point to catch up to the current moment. If remote log storage is off, that changelog tail lives only on the failed tablet server's local disk · which is the disk you just lost. The snapshot, however durably stored, can only restore the state as of its own offset; everything written since then is gone. **The two upload tracks are independent on the way in. The recovery story stitches them back together on the way out, and breaks if either piece is missing.**

One nuance worth ending on, is that most production recoveries aren't full cold restarts.

### Standby Replicas: The Warm Failover Path

Everything we've described so far is the cold-start path; the one that runs when no other copy of a bucket is still alive. In practice, **Fluss replicates each bucket across multiple tablet servers** · one leader handling writes, two or more followers continuously tailing the same log. The followers maintain their own live RocksDB instance, kept current with the leader's in near-real-time.

![](assets/storage_hierarchy/fig6.png)

When the leader fails, the controller picks a follower and promotes it. **That follower's live RocksDB is already current, so traffic resumes in seconds, without S3 download and log replay.** The snapshot path still matters · it's the safety net when an entire replica set is lost at once, when a bucket gets reassigned to a brand-new tablet server, or when you're bootstrapping a fresh follower into the cluster. But that path is the fallback, not the everyday failure handler.

This refines the framing of remote storage. Calling it the recovery substrate and the durability floor was accurate. It just isn't the recovery path you exercise most often in healthy production. **The everyday path is one replica picking up where another left off**, which is precisely why running with replication factor 1 in production is a bad idea, however durable your snapshots are.

## Combining Them
There are four ways to combine remote log storage and lakehouse tiering. Three
are useful, one is a trap.

![](assets/storage_hierarchy/fig7.png)

**Remote off, lakehouse off.** Local disk only. Viable for development, demos, and
tables small enough to fit on local disk for the retention you actually want.
Beyond that, you hit the disk-full failure mode within hours to days.

**Remote on, lakehouse off.** The most common starting point. Production-grade log
retention via S3, no analytical projection. Sensible when Fluss is the durable log
for streaming consumers and not a streaming lakehouse, and a good first step when
adopting Fluss. Get the storage architecture right before adding analytical features.

**Remote off, lakehouse on. The trap.** With the remote-log task disabled, nothing
trims local segments. The lakehouse tiering job ingests through the tablet server
but does **not** trigger local cleanup as a side effect. Worse, since TTL is enforced
only on the remote-tiered copy, no time-based retention applies at all: the local
copy is "everything since the table was created." Local disk grows until writes
start failing. The lakehouse continues working normally meanwhile, which makes
this failure mode confusing to debug · everything looks healthy from the analytical
side until the write path falls over.

**Remote on, lakehouse on.** The full streaming-lakehouse setup. Logs are tiered to
S3, snapshots are uploaded to S3, the tiering service produces a lakehouse projection,
and the lakehouse-confirmation gate adds a second safety layer on top of TTL ·
remote segments are not expired until the lake has confirmed them. This is the
configuration Fluss is designed around.

The PK snapshot track is orthogonal to all of this. It runs on its own cadence
(`kv.snapshot.interval`, default 10 minutes), writes to its own remote subdirectory
(`/kv`), and is what makes PK tables recoverable after disk loss. Disabling remote
log storage does **not** disable KV snapshot upload. Three independent tracks,
three independent config keys · the configuration vocabulary does not make this
obvious.

## Closing Thoughts
Fluss's storage layer is structurally simple · three tiers, two background tasks ·
but the simplicity hides the trap. Tier 1 looks like the only tier that matters
because it is the only one on the live query path. Tier 2 looks like an
implementation detail because it is "just S3". Tier 3 looks like a destination
because it is the lakehouse, where data goes to be queried by everything that is
not Fluss. Each of these mental shortcuts is wrong in a specific way that only
bites after you have configured something based on it.

The mental model that holds up is the one this post argued for. Three tiers
with three different jobs and three different persistence semantics. Two background
tasks that move data out of Tier 1 for two unrelated reasons · disk economics
and cross-engine analytical access · and which you should reason about
independently. A small set of configuration knobs whose defaults are deliberately
the right starting point: remote log storage on, snapshots every ten minutes,
seven-day TTL, three-minute lakehouse freshness target. **Disabling things is almost
always the wrong move.** Tuning the knobs to match your actual workload is the
right one.

Part two of this series goes inside the tiering service itself · the Flink job
that produces the lakehouse projection, its coordinator state machine, the
conditions under which large PK tables struggle to complete a first round, and
what to watch for in steady state. Read on when you're ready.

