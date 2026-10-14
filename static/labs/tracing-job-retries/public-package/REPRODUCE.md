# Neutral Fluss source package

Source-only delivery. This package has not run a cluster, allocated a loop file or earned permission, runtime PASS, cleanup PASS or public readiness. A successful operator run must supply the actual evidence described below. The retained workload README describes older execution; its bytes are preserved, and its linked guide is shipped at `evidence/RUNTIME_README.md`.

## Exact environment and scope

Use an already authorized native Linux x86_64 host with `/usr/bin/python3` 3.10.12, Docker server 29.1.3 linux/amd64 and unchanged `vm.max_map_count=65530`. Existing host tools: Docker CLI, fallocate, findmnt, losetup, mount, umount, sync, fuser and `/usr/sbin/mkfs.ext4`. Do not install host tools or change host configuration. The operator supplies the actual hostname, fresh owned root, run/container/network identity, internal ports and explicit budgets.

Container: `docker.io/library/maven@sha256:82e47241881f23ad774f5db8829efca15758e8fdb5b1d64ea9f8d6420a85068e`, linux/amd64, Java 17, Maven 3.9.9. Install only the retained in-container python3, procps and iproute2 packages; actual Python must be 3.12.3. Maven keeps Fluss client 1.0.0, Jackson 2.18.3, compiler plugin 3.14.0, shade plugin 3.6.0 and the recorded dependency plugin 3.7.0. Archive: `https://downloads.apache.org/fluss/fluss-1.0.0/fluss-1.0.0-bin.tgz`, exactly 522178300 bytes, SHA512 `4cc134d1c5e7b9b07754b4d38903b9c6e4075d66aa7cf04eb3b053fa5095266f1d141e147417d292b3e93b642b24ea06630709de85562c3a829b640ccb7d52ca`. Its official `.sha512` is checked as well. No artifact or dependency substitutions.

Container limits: 8 GiB memory and swap, 3 CPUs, 1024 PIDs, ordinary privileges, no published host ports, json-file logs 4m x 2. Internal operator-declared ports must be coordinator 9123, ZooKeeper 2181 and HTTP fixture 18080; the fresh container gives these their own namespace. The pre-allocation exclusive-slot and foreign-resource checks do not grant use of any unrelated resources.

One new physical 4294967296-byte ext4 file, `mkfs.ext4 -m 0 -E nodiscard`, one loop device and mount with `nosuid,nodev`. Verify allocated blocks before and after format and at each heavy boundary. Bind this mount to `/lab/runtime`. All variable archive, extracted distribution, ZooKeeper, remote data, Maven repository and target paths live there. `data.dir` remains `/lab/runtime/run-02-data`. Before every allocating phase, require resolved paths, all existing ancestors and the nearest existing parent on the exact loop. Reject symlinks, nested/bind mounts, different devices, changed mount IDs, replaced root/ancestor inodes and stale namespace state. The host retains the namespace generation independently of the container state file. Require filesystem capacity between 3.5 and 4 GiB and use below 85% before allocation and after packages, prepare, build, dependencies, start, verify and stop. If it cannot fit, the run fails and keeps owned residue for inspection.

All 15 workload source files remain unchanged. The controller makes a separate build descriptor from the exact POM, inserting only the build directory `/lab/runtime/build-target` and source directory `/lab/source/src/main/java`. Maven runs the same clean/package goals and dependency tree, with `-f /lab/staging/build.pom.xml` and `-Dmaven.repo.local=/lab/runtime/m2`. The exported descriptor and jar/compiler class are independently inspected. Raw process argv remains private; the declared public projection carries operation identities, PIDs, exit/drain and hashes of original process records. The seven cases, 234 assertions, six real SIGKILL exits and recovery job/PID identities remain required.

## Before either terminal mutates anything

Obtain `public-reproduction-fluss-v3.tar.gz`, `bootstrap.py`, their externally supplied SHA256 pins and the external `PUBLIC_MANIFEST.json` SHA256. Pin the seed using a trusted SHA256 implementation. Extract into a fresh absolute directory on the same budgeted filesystem:

```sh
python3 -B /absolute/pinned-bootstrap.py \
  --archive /absolute/public-reproduction-fluss-v3.tar.gz \
  --archive-sha256 PUBLISHED_ARCHIVE_SHA256 \
  --manifest-sha256 PUBLISHED_MANIFEST_SHA256 \
  --destination /var/tmp/fresh-public-source
```

Copy both false templates outside the extracted package. Replace the run ID with `fluss-<operator-token>-<16-lowercase-hex>`, root with `/var/tmp/technical-blogs-<run-id>` and hostname with the actual local hostname. Keep the declared internal ports. Use a fresh separate exchange directory whose existing parent is on the same filesystem as the owned root and Docker root. No file in the extracted package may change.

Public first-time operators explicitly set `baseline` to `{"mode":"fresh"}`. The runner measures its own baseline before creating the owned root, exchange or loop file. A read-only manual probe from the extracted package lets the operator inspect current used bytes and CURRENT foreign containers before making the exact grant:

```sh
cd /var/tmp/fresh-public-source
sudo -n /usr/bin/python3 -B -c 'import json; from pathlib import Path; from supervision import host_sample; from boundaries import foreign,foreign_hash; x=foreign(); print(json.dumps({"sample":host_sample(Path("/var/tmp"),0,0),"foreign":x,"foreign_snapshot_sha256":foreign_hash(x)},indent=2))'
```

For carried accounting, set `baseline` to the following explicit structure. Missing carried files reject; they never select fresh mode. Original baseline bytes and its hash are immutable, even after cleanup or resize:

```json
{"mode":"carried","baseline":{"path":"/absolute/original-baseline.json","sha256":"ORIGINAL_SHA256"},"used_bytes_key":"used_bytes","device_key":"device","peak_chain":{"path":"/absolute/latest-complete-chain.json","sha256":"CHAIN_SHA256"}}
```

The operator chooses the original document's field names explicitly, for example `docker_used_bytes` and `docker_device`. The chain is JSON with `baseline_sha256`, `complete:true`, fresh `at_gst` (within 60 seconds, UTC+04:00), `peak_used_bytes`, and nonempty `observations` of `{path,sha256}` references to integer `peak_used_bytes` records. Its peak must equal the maximum of all supplied peaks and baseline. The external operator must audit completeness against all earlier work, failures, cleanup and current samples; this package cannot discover missing historical files. Reference hashes and the operator grant bind the selected chain. Refresh its freshness before launch without resetting its baseline or dropping observations.

Fill every `outside_budget.limits` entry before allocation. Source/staging: at least 4 MiB. Evidence: 256 MiB. Final archive: 256 MiB. Exchange/index/receipt: 4 MiB. The existing 4 MiB source/staging bound explicitly includes the two bounded 64 KiB workspace identity/state files; required source/helper bytes plus those limits are admitted before copying. They are owned metadata, while every release, cache, target and data allocation remains inside the loop. Supply measured positive upper bounds for newly needed Docker image allocation and container writable allocation, with a pinned external JSON `provenance` explaining how each was measured. Retained images and all other prior allocations remain charged to the baseline. Verifier parses the archive in memory and writes only the bounded receipt; it does not duplicate the evidence onto disk. Initial package staging is external operator work and must already be charged to carried accounting; its copied source/staging budget remains explicit.

Admission requires both the unchanged reservation test `max(P,current_used+4GiB)-B <= 8GiB` and the stronger full-budget test `max(P,current_used+4GiB+outside_total)-B <= 8GiB`. Projected and actual free space must remain at least 25 GiB, usage ceil below 94%, preboot available memory at least 10 GiB and active available memory at least 2 GiB. One monitor samples every 5 seconds and spans allocation, bootstrap, actual workload, cleanup, export and receipt return. Sampling is not a hard filesystem quota. Evidence is bounded at 256 MiB, native Fluss logs at 64 MiB, each command stream at 32 MiB. Outside budgets are also checked; new image host-used delta and writable layer bytes cannot exceed their operator limits.

The operator's real authorization remains external. Bind `approved:true`, operator/decision provenance, manifest, exact root/run ID, exact scope string from the false template, CURRENT foreign snapshot SHA, exact baseline mode/provenance and exact outside budget to the specific decision. This authorizes only owned allocation/mount/container/network/cleanup. Do not distribute a true grant with this package. No credentials, certificates, private host, prior-suite receipts or other operator's authorization are needed.

## Terminal 1: continuous lifecycle

```sh
cd /var/tmp/fresh-public-source
sudo -n /usr/bin/python3 -B public_run.py \
  --manifest-sha256 PUBLISHED_MANIFEST_SHA256 \
  --operator-config /absolute/operator-config.json \
  --operator-authorization /absolute/operator-authorization.json \
  --exchange-dir /var/tmp/fresh-exchange
```

Do not run the older workload fragments separately. The fixed order is prepare, build, dependency tree, start, verify and stop. Original phase timeouts remain 800/1250/350/150/650/90 seconds, command and collector cancellation bounds remain unchanged, whole lifecycle deadline 3600 seconds. The receipt wait is at most 300 seconds and is inside that whole deadline. Start terminal 2 promptly when `offer.json` appears.

Fresh owned paths: root `source/`, `staging/`, `evidence/`, empty host `runtime/`, `data4GiB.ext4`, `data-mount/`, ownership markers. Container bindings: root to `/lab`, exact source to `/lab/source`, loop mount to `/lab/runtime`. Cleanup stops and removes only the exact owned container/network, syncs and unmounts the exact owned mount, detaches its sole loop and deletes its verified inode. Sources, staging, evidence and Docker images stay retained and budgeted. No pruning or deletion of unrelated state. Every boundary compares the fresh initial CURRENT foreign set, including during receipt wait.

On failure or cancellation, registered owned process groups are cancelled, then only the owned container is stopped before diagnostics. The runner fails and retains its owned residue; do not infer cleanup from a failed run, and do not manually remove a changed/borrowed mount or file. Cancellation/guard/collector/receipt failure cannot create successful lifecycle credit.

## Terminal 2: independent archive inspection and receipt

Use a separate process with the same pinned fresh package, while terminal 1 still monitors. Read the offered archive SHA and inspect the actual archive using the shipped verifier:

```sh
cd /var/tmp/fresh-public-source
sudo -n /usr/bin/python3 -B verify_export.py \
  --offer /var/tmp/fresh-exchange/offer.json \
  --manifest-sha256 PUBLISHED_MANIFEST_SHA256 \
  --receipt-target /var/tmp/fresh-exchange/receipt.json
```

The verifier hashes the real bounded archive, rejects links/traversal/duplicate members and checks exact index/package/source bytes, real jar/compiler output, 234 expected/observed assertion hash pairs, six killed/recovery job hash identities, the surviving fixture, storage/caps/path generations, natural phase exits/drain, projected monitor samples and exact cleanup identities/absence observations. It accepts only the closed `fluss-public-projection-v1` schemas. Unknown or nested fields, duplicate JSON keys, arbitrary diagnostic streams and extra evidence members reject even when their archive/index hashes are recomputed. The manifest, index, offer and receipt explicitly bind projection.py, verification.py and public_schema.py as well as verify_export.py. Only then it atomically returns a nonce/run/archive/index/source-bound v2 receipt. Terminal 1 rejects missing, late or mismatched receipts and verifies CURRENT foreign preservation again while the same monitor is alive.

Full Docker inspect, Config/HostConfig/Env, operator inputs/approval, baseline/host/preflight/boundary records, private transport/process argv, configuration and native diagnostic text remain PRIVATE in the owned evidence directory. Share only the one bounded projected archive. Its approved workload stream is schema-limited JSONL containing worker/channel/line IDs, byte lengths, line SHA256 and finite event-kind tags. It never includes arbitrary stdout/stderr text. Public assertions expose expected/observed hashes, not arbitrary nested values. Original streams and assertions remain private and hash-bound for an authorized private audit. This projection validates consistency of the declared observations; it does not attest an operator's honesty or independently reconstruct redacted bytes. A runtime audit must inspect private raw provenance separately. No privacy claim relies on canary scanning or secret regexes.

After terminal 1 naturally exits zero, retain the one `evidence.tar.gz`, `offer.json`, returned `receipt.json`, owned `evidence/lifecycle-result.json`, and `evidence/lifecycle.completion.json`. Keep offer.json private because it identifies the local exchange path. Require no error, monitor drained, receipt hash matching its actual file and monitor alive at receipt. Independently record terminal 2's actual natural exit zero and drained output; its receipt does not predict its future exit. A source-only local completion is not an actual host/runtime completion; independent runtime review and consumption remain external gates.
