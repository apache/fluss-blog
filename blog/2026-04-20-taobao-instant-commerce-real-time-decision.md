---
slug: taobao-instant-commerce-real-time-decision
title: "Taobao Real-Time Decisions at Scale with Fluss"
sidebar_label: "Taobao Instant Commerce: Real-Time Decisions at Scale with Fluss"
authors: [jark]
---

In autumn 2025, the viral social media trend of "The First Cup of Milk Tea in Autumn" swept through online platforms once again.
With a simple tap on their screens, consumers had their beverages delivered within 30 minutes.
This seemingly effortless moment reflects how Taobao Instant Commerce has evolved from a single-category food delivery service into a high-frequency core business covering all scenarios — including fresh produce, consumer electronics (3C), and beauty products.
Its business model is now driven by a dual engine: "Daily High-Frequency Consumption" and "Event-Driven Peak Bursts."

Under this pressure, "real-time" has become the lifeline for operational decision-making, algorithm iteration, and quality monitoring:

- **Operations:** Refresh conversion rates and funnels within 30 seconds.
- **Algorithms:** Require order prediction models to iterate at minute-level granularity.
- **Quality Assurance:** Demands sub-second visibility for canary release discrepancies and instant alerting for anomalies.

The traditional pipeline had long operated on an architecture comprising Kafka, Flink, Paimon, and StarRocks.
As business scale continued to expand, three core bottlenecks became increasingly prominent: expanding state sizes for dimension tables, complex wide-table joins, and high resource consumption for lake-warehouse synchronization.
These challenges created an "impossible triangle" of latency, consistency, and cost-efficiency.

With the introduction of Apache Fluss, these pain points were systematically resolved through the synergistic implementation of its key features: **Delta Join**, **Partial Update**, **Streaming & Lakehouse Unification**, **Column Pruning**, and **Auto-Increment Columns**.

<!-- truncate -->

## The "Impossible Triangle" Dilemma: Business Pain Points & Technical Challenges

The real-time data system of Taobao Instant Commerce must reliably process ultra-large-scale, high-concurrency real-time data streams.
It must also build real-time wide tables across multiple business domains and support core pipelines such as the real-time association of page view streams with order streams, as well as canary monitoring.
This imposes extreme requirements on latency, consistency, cost-efficiency, and system scalability.

Under the traditional technology stack, the challenges across these four dimensions are deeply intertwined, ultimately forming a trilemma where all three cannot be simultaneously optimized.

The root cause lies in stream-batch separation at the storage layer: Kafka as the message queue represents the "stream" abstraction, while Paimon as the lakehouse format represents the "batch" abstraction.
Bridging these two relies heavily on numerous Flink ETL jobs acting as a "glue layer." Each additional layer compounds latency, increases costs, and heightens data consistency risk.

### Four Core Business Issues
![](assets/taobao_realtime_decisions/issues.png)

### Three Core Pain Points of the Traditional Tech Stack

- **Surging Memory Pressure from Dual-Stream Joins:** Kafka lacks native support for dimension table lookups. Order information had to be fully loaded into Flink State. During promotional events, over 100 million orders caused the state size of single jobs to surge to hundreds of GBs, leading to checkpoint timeouts and frequent task failures.

- **Fan-Out Pipeline Complexity in Wide Table Construction:** The product-store analysis wide table depended on 5+ upstream systems. Using Kafka required writing to a new Topic after every join operation, resulting in an overly complex pipeline with extremely high operational and maintenance costs.

- **Core Resource Drain from Lakehouse Synchronization:** Each table synced to Paimon required maintaining an independent Flink ingestion job. During peak events, dozens of these "data transfer" jobs ran simultaneously, competing with core computing tasks for resources and causing overall performance degradation.

![](assets/taobao_realtime_decisions/arch.png)

### Architecture Selection: From "Compute-Layer Stitching" to "Storage-Layer Unification"

The core principle for our technology selection: **the breakthrough lies not in the compute layer, but in the storage layer.**

Fluss's design philosophy directly addresses these pain points through Stream-Batch Unification at the storage layer.
It is not merely another message queue — it converges streaming consumption and batch querying into a single distributed storage kernel.
Streaming and batch operations require no data replication, no format conversion, and no additional ETL jobs.
This fundamental shift directly eliminates the three primary sources of latency, cost, and consistency risks inherent in traditional pipelines.

## Fluss Core Scenario Implementation

Taobao Instant Commerce has designed a three-layer overall architecture by leveraging Fluss's five core features tailored to business needs.
This establishes Fluss as the unified data foundation for real-time decision-making, integrating the full pipeline — from data ingestion and stream-batch processing to lakehouse storage and service delivery.

### Three-Layer Overall Architecture

![](assets/taobao_realtime_decisions/3_layer_arch.png)

The real-time data system is structured into three layers:

- **Data Source Layer:** Integrates all business data sources — including order streams, visit streams, product dimension tables, and inventory/price streams — and uniformly writes them into Fluss's Log Tables or KV Tables.

- **Fluss Storage & Compute Layer:** Achieves unified data storage via Fluss's Log/KV Tables. Leverages Delta Join, Partial Update, and Streaming-Lakehouse Unification (Auto-Tiering) to handle real-time computation, multi-table joins, wide table construction, and lakehouse synchronization. Provides stateless computing support for Flink, significantly reducing state management overhead.

- **Business Service Layer:** Leveraging a unified data view from both Fluss and lakehouse storage (Paimon), this layer delivers data services to operational real-time dashboards, algorithmic order prediction models, canary monitoring systems, and product-store analysis systems, enabling real-time, sub-second decision support.

### Five Core Scenarios and Feature Combination Matrix

| **Core Scenario** | **Core Business Pain Points** | **Fluss Feature Combination** | **Key Benefits** |
| --- | --- | --- | --- |
| Real-time Conversion Rate & Order Attribution | Bloated Dimension Table State; Checkpoint Timeouts | KV Table + Delta Join + Server-side Column Pruning | In-memory State: TB-level to ~0; Checkpoint: Minutes to Seconds; Query Latency: Hundreds of ms to Milliseconds |
| Product-Store Real-time Wide Tables | Complex Multi-stream Joins; I/O Waste; High Pipeline Coupling | KV Table + Partial Update | Write Latency: Second-level jitter to stable sub-second; Network I/O: Saves 50%+ |
| Real-time Order Prediction | Difficulty in Stream-Batch Fusion; Numerous Data Transfer Jobs | KV Table + Lakehouse-Streaming Unification (Tiering) | Pipeline Shortening: Reduces redundant hops by 50%; Resource Savings: 30%+ |
| Canary Monitoring | Severe I/O Waste; Multi-hop Synchronization Links | Log Table + Server-side Column Pruning + Auto-Tiering | Network I/O: Saves ~67%; Alert Speed: Seconds to sub-seconds |
| Global Real-time UV Statistics | Hologres Lookup Hotspot Bottlenecks; Flink State Bloat | KV Table (Auto-Increment) + Agg Table / Lakehouse-Streaming Unification | State Overhead: TB-level to KB/MB-level; Lookup Latency: Milliseconds to Microseconds |

---

## Scenario 1: Real-Time Conversion Rate & Order Attribution

Conversion Rate (the ratio of purchasing users to visiting users) is a core metric for measuring conversion efficiency in Taobao Instant Commerce.
Its calculation relies on the real-time join of user visit streams with order streams.

### Pain Points of Traditional Solutions
![](assets/taobao_realtime_decisions/painpoints.png)
In the legacy architecture, a Flink Regular Join must continuously accumulate all unexpired events in its local state to match orders with browsing records.
This creates an architectural dilemma: extending the conversion observation window incurs linearly growing storage costs.

- **Massive State Bloat & Compaction Pressure:** During promotional events, hundreds of billions of access logs require retention within long windows. Total State for a single job exceeded TB levels, leading to severe RocksDB compaction pressure and extremely long checkpoint durations.
- **I/O Saturation & Latency Degradation:** Amplified State read/write operations saturated disk I/O. Real-time attribution latency degraded from seconds to minutes.
- **Checkpoint Failures & High RTO:** Checkpoint durations deteriorated from minutes to 10–15 minutes, frequently causing timeouts and failures.
- **Limited Attribution Window:** The effective association time window was constrained by local storage capacity, making it impossible to support long-cycle "Browse-to-Order" conversion attribution.

### Architecture Based on Fluss Delta Join

![](assets/taobao_realtime_decisions/delta.png)

The solution upgrades the conventional Flink dual-stream join to a **Delta Join**. This approach offloads the full volume of dual-stream data from Flink State to Fluss KV Tables (backed by RocksDB), implementing bidirectional Prefix Lookup for a near-stateless dual-stream join.

- **Dual KV Table Ingestion with Composite Keys:** The real-time order stream is written to a Fluss KV Table with `PRIMARY KEY (user_id, ds, order_id)` and `bucket.key = 'user_id'`. Simultaneously, real-time traffic visit logs are written to a Fluss KV Table with `PRIMARY KEY (user_id, ds)` and `bucket.key = 'user_id'`. Both tables use a composite primary key design where the join key serves as the bucket key, enabling efficient Prefix Lookup.

- **Stateless Bidirectional Join via Delta Join Operator:** Leveraging the Delta Join operator in Flink 2.1+, incoming orders trigger lookups in the visit log table, and incoming visits trigger lookups in the order table. Flink calculates the target `bucketId` using `MurmurHash(bucket.key)` to route RPC requests precisely to the single Fluss TabletServer holding that bucket's RocksDB instance.

- **Real-Time Attribution & Lakehouse Sync:** The joined results are written to a Fluss wide table and automatically synchronized to Paimon via the Streaming-Lakehouse Unification mechanism.

### Core DDL and Join SQL

```sql
-- Order Stream (Right Table in Join)
CREATE TABLE `fluss_catalog`.`db`.`order_ri` (
    order_id STRING,
    user_id STRING,
    order_time STRING,
    pay_amt STRING,
    ds STRING,
    PRIMARY KEY (user_id, ds, order_id) NOT ENFORCED
) PARTITIONED BY (ds)
WITH (
    'bucket.key' = 'user_id',
    'bucket.num' = '${BUCKET_NUM}',
    'table.auto-partition.enabled' = 'true',
    'table.auto-partition.key' = 'ds'
);

-- Visit Stream (Left Table in Join)
CREATE TABLE `fluss_catalog`.`db`.`log_page_ri` (
    user_id STRING,
    first_page_time STRING,
    pv BIGINT,
    ds STRING,
    PRIMARY KEY (user_id, ds) NOT ENFORCED
) PARTITIONED BY (ds)
WITH (
    'bucket.key' = 'user_id',
    'bucket.num' = '${BUCKET_NUM}',
    'table.auto-partition.enabled' = 'true',
    'table.auto-partition.key' = 'ds'
);

-- Sink Table
CREATE TABLE `fluss_catalog`.`db`.`log_page_ord_detail_ri` (
    `user_id`         STRING COMMENT 'User ID',
    `order_id`        STRING COMMENT 'Order ID',
    `first_page_time` STRING COMMENT 'First Visit Time',
    `order_time`      STRING COMMENT 'Order Placement Time',
    `pv`              BIGINT COMMENT 'Page Views',
    `pay_amt`         STRING COMMENT 'Payment Amount',
    `is_matched`      STRING COMMENT 'Match Status',
    `ds`              STRING COMMENT 'Date Partition',
    PRIMARY KEY (user_id, order_id, ds) NOT ENFORCED
)
PARTITIONED BY (ds)
WITH (
    'bucket.key' = 'user_id,order_id',
    'bucket.num' = '${BUCKET_NUM}',
    'table.auto-partition.enabled' = 'true',
    'table.auto-partition.key' = 'ds',
    'table.datalake.enabled' = 'true',    -- Enable Streaming-Lakehouse Unification
    'table.datalake.freshness' = '3min'   -- Controls Lakehouse Table Freshness
);
```

The Delta Join implementation:

```sql
CREATE TEMPORARY VIEW matched_page_ord_detail AS
SELECT
    l.ds,
    l.user_id,
    l.first_page_time,
    l.pv,
    o.order_id,
    o.order_time,
    CASE WHEN o.order_time >= l.first_page_time THEN '1' ELSE '0' END AS is_matched
FROM `fluss_catalog`.`db`.`log_page_ri` l
LEFT JOIN `fluss_catalog`.`db`.`order_ri` o
    ON l.user_id = o.user_id AND l.ds = o.ds;
```

### Results

![](assets/taobao_realtime_decisions/results.png)

## Scenario 2: Real-Time Product-Store Wide Table — Efficient Column-Level Updates via Partial Update

The Real-time Product-Store Wide Table must aggregate four core behavioral streams — impressions, clicks, visits, and orders — in real time, outputting key metrics across both "Product" and "Store" dimensions.

### Pain Points of Traditional Solutions
![](assets/taobao_realtime_decisions/painpoints2.png)

The legacy solution constructed the wide table using Flink multi-stream joins over Kafka topics, resulting in a complex fan-in architecture with the following core pain points:

- **Full-Row Write I/O Waste:** Even if only a single behavior metric is updated, the system must write all 100+ columns of the full row, causing severe redundancy in both network and storage I/O.
- **High Operational Complexity:** Adding a new field necessitates modifications across multiple jobs, significantly increasing operational overhead.
- **Latency Coupling (Straggler Problem):** The write latency of the wide table is determined by the slowest upstream stream.
- **State Bloat:** Flink must cache massive amounts of intermediate state locally, leading to TB-scale state bloat, checkpoint timeouts, and OOM risks.

### Architecture Based on Fluss Partial Update
![](assets/taobao_realtime_decisions/solution2.png)

Fluss KV Tables serve as the unified storage for a multi-dimensional wide table. By leveraging **Partial Update**, each Flink job is responsible solely for aggregating its specific behavioral metrics and writing to the target columns, eliminating the need for complex multi-stream joins.
The field-level merging is automatically handled by the RowMerger on the Fluss server side.

- **Independent Aggregation & Ingestion:** Five or more upstream behavior streams run as independent Flink jobs, each consuming only a single type of behavior log and writing exclusively to its corresponding metric columns.
- **Server-Side Intelligent Column-Level Merging:** Fluss leverages BitSet bitmap technology to identify target columns in write requests, reading and updating only target columns while non-target columns retain their historical values in RocksDB.
- **Online Schema Evolution:** When new statistical metrics are required, teams simply execute an `ALTER TABLE ADD COLUMN` DDL statement without downtime or restarting existing jobs.

### Core DDL and Per-Job Write Implementation

```sql
CREATE TABLE shop_stat_wide (
    shop_id   BIGINT NOT NULL,
    stat_date STRING NOT NULL,
    stat_hour STRING NOT NULL,
    exp_cnt   BIGINT,   -- Exposure Count
    page_cnt  BIGINT,   -- Page View Count
    PRIMARY KEY (shop_id, stat_date, stat_hour) NOT ENFORCED
) WITH (
    'bucket.num' = '${BUCKET_NUM}',
    'bucket.key' = 'shop_id'
);

-- Write Exposure Data
INSERT INTO shop_stat_wide (shop_id, stat_date, stat_hour, exp_cnt)
SELECT shop_id, stat_date, stat_hour, SUM(exp_cnt) AS exp_cnt
FROM exposure_log
GROUP BY shop_id, stat_date, stat_hour;

-- Write Visit Data
INSERT INTO shop_stat_wide (shop_id, stat_date, stat_hour, page_cnt)
SELECT shop_id, stat_date, stat_hour, SUM(page_cnt) AS page_cnt
FROM page_log
GROUP BY shop_id, stat_date, stat_hour;
```

### Results
![](assets/taobao_realtime_decisions/results2.png)

## Scenario 3: Real-Time Order Prediction — Efficient Data Fusion via Lake-Stream Unification

Real-time order forecasting serves as a cornerstone of Taobao Instant Commerce's algorithmic decision-making framework.
During promotional events, the system iterates the prediction model every minute to accurately project the total daily GMV, enabling dynamic adjustments to subsidy strategies and inventory allocation.

![](assets/taobao_realtime_decisions/scenario3.png)

### Architecture Based on Fluss Lake-Stream Unification
![](assets/taobao_realtime_decisions/arch3.png)

Fluss KV Tables serve as a unified storage layer for both streaming and batch processing. Integrating Streaming-Lakehouse Unification enables automated synchronization to the data lake, with data consistency inherently guaranteed since both streaming and batch operations rely on the same KV Table.

- **Real-time Accumulation:** The real-time order stream is written into the Fluss KV Table, enabling calculation of rolling cumulative order counts on a per-minute basis via stream reads.
- **Efficient Stream-Batch Fusion:** A Flink UDF directly reads both real-time data (via stream read) and historical baseline data (via batch read / Snapshot Lookup) from the Fluss KV Table.
- **Low-Latency Lake Sync:** Model prediction results are written back to the Fluss KV Table with automatic Tiering enabled.
- **Unified Data Consistency:** Downstream algorithm models and operational dashboards read real-time results from Fluss and historical results from Paimon, ensuring end-to-end consistency.

### Core DDL

```sql
-- Real-time Order Minute-Accumulation Stream
CREATE TABLE `fluss_catalog`.`db`.`order_dtm` (
  `ds`           STRING COMMENT 'Day Partition',
  `mm`           STRING COMMENT 'Minute',
  `order_source` STRING COMMENT 'Order Source',
  `order_cnt`    BIGINT COMMENT 'Order Count',
  PRIMARY KEY (ds, mm, order_source) NOT ENFORCED
)
PARTITIONED BY (ds)
WITH (
  'bucket.key' = 'mm,order_source',
  'bucket.num' = '${BUCKET_NUM}',
  'table.auto-partition.enabled' = 'true',
  'table.auto-partition.time-unit' = 'day',
  'table.auto-partition.key' = 'ds',
  'table.auto-partition.num-retention' = '2',
  'table.log.arrow.compression.type' = 'zstd'
);

-- Order Forecast Stream (with Streaming-Lakehouse Unification)
CREATE TABLE `fluss_catalog`.`db`.`order_forecast_mm` (
  `ds`                        STRING COMMENT 'Date Partition',
  `mm`                        STRING COMMENT 'Minute',
  `order_source`              STRING COMMENT 'Order Source',
  `cumulative_order_cnt`      BIGINT COMMENT 'Cumulative Order Count',
  `forecast_daily_order_cnt`  STRING COMMENT 'Predicted Total Daily Order Volume',
  PRIMARY KEY (ds, mm, order_source) NOT ENFORCED
)
PARTITIONED BY (ds)
WITH (
  'bucket.key' = 'mm,order_source',
  'bucket.num' = '${BUCKET_NUM}',
  'table.auto-partition.enabled' = 'true',
  'table.auto-partition.time-unit' = 'day',
  'table.auto-partition.key' = 'ds',
  'table.auto-partition.num-retention' = '2',
  'table.log.arrow.compression.type' = 'zstd',
  'table.datalake.enabled' = 'true',   -- Enable Streaming-Lakehouse Unification
  'table.datalake.freshness' = '30s'   -- Controls Lakehouse Table Freshness
);
```

### Results

| **Core Metric** | **Legacy (Kafka + Independent ETL)** | **Fluss Lake-Stream Unification** | **Improvement** |
| --- | --- | --- | --- |
| Data Pipeline Hops | 4 Hops | 2 Hops | 50% reduction in pipeline length |
| Additional Flink Job Count | 4 Jobs | 2 Jobs | 50% reduction in operational overhead |
| Latency: Results to Paimon | ~5 minutes | < 2 minutes | 2.5x improvement in data ingestion latency |
| Flink CU (Compute Unit) Savings During Campaigns | — | ~30% | Significantly reduces computational resource costs |
| Model Iteration Data Latency | > 1 minute | < 30 seconds | Supports high-frequency model tuning |

---

## Scenario 4: Canary Release Monitoring — Efficient Log Processing via Log Table and Column Pruning

Frontend telemetry data covering the full user journey serves as the core basis for evaluating release quality, monitoring marketing effectiveness, and optimizing search and recommendation strategies.
Canary releases have become the standard procedure, with canary monitoring acting as the critical "safety valve" — aimed at detecting anomalies within seconds.

### Pain Points of Traditional Solutions
![](assets/taobao_realtime_decisions/painpoints3.png)

| **Dimension** | **Specific Technical Challenge** |
| --- | --- |
| I/O Resource Waste | Kafka carries complete message payloads with no server-side column filtering. Monitoring tasks require only ~30 core fields, yet must deserialize entire messages containing large fields like `args` (90+ columns). |
| Redundant & Complex Pipeline | Two independent Flink jobs must be maintained: one for real-time monitoring and alerting, and another for data cleaning and ingestion into Paimon. |
| Multi-Source Data Silos | Canary logs from multiple client endpoints are processed in isolation with scattered logic. |

### Architecture Based on Fluss Log Table and Column Pruning

![](assets/taobao_realtime_decisions/arch4.png)

To address the aforementioned pain points, Taobao Instant Commerce underwent a three-stage architectural evolution, ultimately establishing a unified log governance solution centered on Fluss:
* **Phase 1:** Introduced Fluss for a specific client’s data to validate the feasibility of cost optimization and improvements in data freshness. 
* **Phase 2:** Integrated data from all client endpoints. While this achieved unified data ingestion, computational tasks remained redundant due to difficulties in reusing the intermediate layer. 
* **Phase 3:** Leveraged Fluss’s server-side column pruning to eliminate invalid I/O, and used automatic Tiering to merge monitoring and synchronization pipelines. This completely resolved the issue of redundant computations.

![](assets/taobao_realtime_decisions/arch5.png)

The new architecture establishes Fluss Log Tables as the single source of truth, creating an efficient closed loop with "write once, multi-dimensional reuse":

The new architecture establishes Fluss Log Tables as the single source of truth, creating an efficient closed loop characterized by "write once, multi-dimensional reuse":
* **Unified High-Throughput Ingestion:** Multi-source canary logs are uniformly written into Fluss Log Tables. Leveraging the Append-Only nature of Log Tables, the system perfectly accommodates high-concurrency write scenarios for massive volumes of logs. 
* **Server-Side Column Pruning:** During Flink consumption, Projection Pushdown pushes the required columns down to the Fluss server side. The server reads and returns only the specified 30 core fields, blocking 67% of invalid network transmission at the source. 
* **Automated Archiving via Streaming-Lakehouse Unification:** By simply enabling the table.datalake.enabled configuration, the system automatically asynchronously synchronizes real-time data to Paimon. This eliminates the need for deploying separate Flink archiving jobs. Real-time monitoring and offline analysis share the same data pipeline, achieving seamless stream-batch data fusion. 
* **Multi-Client Reuse & Second-Level Alerting:** Real-time monitoring tasks directly consume the lightweight, pruned data stream, integrating with FBI dashboards to achieve second-level anomaly alerting. Offline analysis queries Paimon tables directly, ensuring inherent consistency between streaming and batch data.

### Core DDL

```sql
CREATE TABLE `fluss_catalog`.`db`.`log_page_ri` (
  `col1` STRING,
  `col2` STRING,
  -- ... additional columns ...
  ds STRING
)
PARTITIONED BY (ds)
WITH (
  'bucket.num' = '${BUCKET_NUM}',
  'table.auto-partition.enabled' = 'true',
  'table.auto-partition.time-unit' = 'day',
  'table.auto-partition.key' = 'ds',
  'table.auto-partition.num-retention' = '1',
  'table.log.ttl' = '${LOG_TTL}',
  'table.replication.factor' = '${REPLICATION_FACTOR}',
  'table.log.arrow.compression.type' = 'zstd',
  'table.datalake.enabled' = 'true',   -- Enable Streaming-Lakehouse Unification
  'table.datalake.freshness' = '3min'  -- Control lake table data freshness
);

-- Monitoring Query (reads only 30 core columns to trigger server-side column pruning)
INSERT INTO `fluss_catalog`.`db`.ads_gray_monitoring_ri
SELECT col1, col2, col3, col4, ds
FROM `fluss_catalog`.`db`.`log_page_ri`
WHERE KEYVALUE(`args`, ',', '=', 'release_type') = 'grey';
```

### Results
![](assets/taobao_realtime_decisions/results4.png)


## Scenario 5: Global Real-Time UV Statistics — Auto-Increment Columns and Agg Tables for Unique User Counting

In Taobao Instant Commerce’s refined operational framework, Unique Visitors (UV) across the full user journey—covering impressions, visits, clicks, and orders—are core metrics for measuring traffic quality and conversion efficiency. In early architectural practices, we adopted a hybrid stack comprising Flink + Hologres + Paimon + StarRocks:
* Hologres stored user mapping tables to handle ID resolution; 
* Flink constructed Bitmaps via custom UDFs and wrote them to Paimon; 
* StarRocks accelerated queries using materialized views.

However, under ultra-large-scale data scenarios, this architecture exposed three critical pain points: 
* Hotspot Bottlenecks in Hologres Lookups; 
* Backpressure caused by Flink State Bloat; 
* High Synchronization Latency in Paimon.

These issues made it difficult to meet the requirement for second-level real-time monitoring during promotional events. The introduction of Fluss marks a key iteration of this architecture: 
* It replaces Hologres with Fluss KV Tables for low-latency ID mapping; 
* It replaces Flink State with Fluss Agg Tables for stateless local aggregation; 
* It replaces the independent Paimon synchronization pipeline with Auto Tiering for second-level sync.

This solution achieves an architectural upgrade from a fragmented, high-latency multi-component stack to a unified, low-latency Streaming-Lakehouse architecture.

### Pain Point of the Old Approach
![](assets/taobao_realtime_decisions/painpoints4.png)
The pre-iteration architecture suffered from the following critical bottlenecks:
* Hologres Lookup Hotspots and Network Bottlenecks: Flink issued massive volumes of RPC requests to Hologres. Under high concurrency, this led to data skew and hotspots, causing Lookup latency to degrade to the second level. 
* Flink State Bloat and Checkpoint Failures: Flink UDFs were required to maintain TB-scale Bitmap State. This resulted in excessively long Checkpoint durations (>10 minutes), frequent timeouts, and poor job stability. 
* Paimon Synchronization Latency: Paimon Compaction introduced minute-level latency, resulting in insufficient data freshness for downstream StarRocks Materialized Views (SR MVs). This failed to meet the requirements for second-level monitoring.

### Architecture Based on Fluss Auto-Increment Columns and Agg Tables
![](assets/taobao_realtime_decisions/arch6.png)

To address the three major pain points of the traditional architecture, we leveraged Fluss’s core design with a strategy centered on "converting sparse business IDs into dense physical ID bitmaps." Through practices such as full-map pre-loading, auto-increment ID densification, sharded parallelism, and 32-bit Bitmap optimization, we achieved high-performance real-time UV statistics.

* **Auto-Increment KV Mapping Layer:** Leveraging Flink’s native KV index drive, we built real-time dimension association capabilities:
  * **Lock-Free Segment Allocation:** Fluss employs a mechanism where ID segments are requested in batches on-demand via local caching. This thread-level lock-free allocation effectively avoids lock contention and GC jitter during concurrent writes, significantly optimizing ID generation performance. 
  * **Query-Then-Insert:** In dimension table Lookup scenarios, if a business ID is not found, Fluss automatically triggers an INSERT and returns the new auto-increment ID. This mechanism merges the traditional "check-then-write" two-step interaction into a single request, effectively reducing network traffic consumption and cluster pressure. 
  * **Batching & Pipeline Optimization:** By combining Flink’s asynchronous Lookup batch request mechanism with Fluss client-side Pipeline writes, massive discrete RPCs are aggregated and processed in parallel. This design reduces interaction overhead and further optimizes overall system throughput. 
  * **Full Pre-loading & ID Densification:** Before going live, billions of historical business IDs were batch-imported into the Fluss KV Table (dictionary table) to generate unique 64-bit physical IDs using the auto-increment column. This eliminates cross-cluster RPC latency for historical users (100% hit rate in the mapping table), while dynamically assigning IDs via INSERT for new users upon their first appearance.
* **Sharded Parallelism:** By taking the modulus of the physical ID, all users are uniformly distributed across N logical shards, enabling localized parallelism for global deduplication tasks. Since behaviors from the same user strictly fall into the same shard, data volume across shards remains absolutely balanced, completely avoiding hotspot skew caused by patterns in business ID ranges. 
* **32-Bit Dimensionality Reduction & Compression:** When the total number of physical IDs is less than 4 billion, 64-bit IDs can be compressed into 32-bit integers, enabling the use of the rbm32 aggregation function. Compared to rbm64, this solution reduces memory usage by over 50% and significantly improves bitwise operation efficiency and CPU cache hit rates.

#### Dual-Path Aggregation Architecture

Based on the aforementioned preprocessing, the team implemented two parallel data pipelines: 
* **Option A (Fluss Agg Table Pre-Aggregation):** The server side performs local Bitmap merging based on (ds, hh, mm, shard_id), allowing Flink to consume only the aggregated results. This approach offloads computational pressure to the storage layer and is ideal for extreme real-time scenarios (such as war rooms during promotional events), achieving sub-second latency. 
* **Option B (Fluss Auto Tiering + StarRocks Native Deduplication):** Detailed data is synchronized to Paimon at second-level latency, with StarRocks handling the final deduplication. This approach is suitable for flexible multi-dimensional analysis scenarios (such as daily operational dashboards), supporting ad-hoc queries across arbitrary dimensions.

Both paths share the same ID mapping and sharding logic, allowing the team to freely switch between them based business requirements for "real-time performance" versus "query flexibility."
### Core DDL

```sql
-- User Mapping Table (with Auto-Increment Column)
CREATE TABLE `fluss_catalog`.`db`.`user_mapping_table` (
  user_id    BIGINT COMMENT 'Original User ID',
  uid_int64  BIGINT COMMENT 'Auto-incremented Globally Unique Integer ID',
  update_time TIMESTAMP(3) COMMENT 'Update Time',
  PRIMARY KEY (user_id) NOT ENFORCED
) WITH (
  'bucket.key' = 'user_id',
  'bucket.num' = '${BUCKET_NUM}',
  'auto-increment.fields' = 'uid_int64',  -- Enable auto-increment column
  'table.log.arrow.compression.type' = 'zstd'
);

-- Option A: Fluss Agg Table
CREATE TABLE IF NOT EXISTS `fluss_catalog`.`db`.`ads_uv_agg` (
    ds        STRING COMMENT 'Date partition yyyyMMdd',
    hh        STRING COMMENT 'Hour HH',
    mm        STRING COMMENT 'Minute mm',
    shard_id  INT    COMMENT 'Shard ID',
    uv_bitmap BYTES  COMMENT 'Minute-level user bitmap',
    PRIMARY KEY (ds, hh, mm, shard_id) NOT ENFORCED
)
PARTITIONED BY (ds)
WITH (
    'bucket.key' = 'shard_id',
    'bucket.num' = '${BUCKET_NUM}',
    'table.merge-engine' = 'aggregation',
    'fields.uv_bitmap.agg' = 'rbm32',  -- Bitmap Union aggregation
    'table.auto-partition.enabled' = 'true',
    'table.auto-partition.time-unit' = 'day',
    'table.auto-partition.key' = 'ds'
);

-- Option B: Fluss Tiering + StarRocks
CREATE TABLE fluss_catalog.db.ads_uv_detail (
    ds        STRING,
    shard_id  INT,
    uid_int32 INT,
    PRIMARY KEY (ds, shard_id, uid_int32) NOT ENFORCED
) WITH (
    'table.datalake.enabled' = 'true',   -- Enable Streaming-Lakehouse Unification
    'table.datalake.freshness' = '10s'   -- Second-level synchronization
);
```

### Results
![](assets/taobao_realtime_decisions/results5.png)

* If the business prioritizes extreme real-time performance and has fixed aggregation logic, Solution A is recommended, as it pushes the computational load down to the storage layer to the greatest extent. 
* If the business requires flexible multi-dimensional analysis and can tolerate second-level latency, Solution B is recommended, as it fully leverages StarRocks' OLAP capabilities, resulting in a simpler and more universal architecture.

By adopting these two solutions, Taobao Instant Commerce successfully achieved real-time, precise, and cost-effective statistics for full-link UV metrics in ultra-large-scale data scenarios. This approach not only retains StarRocks' query advantages but also resolves upstream pipeline performance bottlenecks through Fluss.

## Fluss Implementation Best Practices and Future Roadmap
During the implementation of Fluss, Taobao Instant Commerce progressed from single-feature pilots to full-pipeline practices involving multi-feature synergy. This process has yielded replicable implementation experience, while also establishing a clear future roadmap aligned with business needs and community development.

### Key Lessons Learned
* **Prioritize DDL Standards:** When creating wide tables, plan the responsible jobs for each column in advance. All non-primary key columns must be declared as NULLABLE, and writers should specify only the target columns. This standard must be integrated into the team’s table creation workflow to prevent update failures caused by improper field configurations. 
* **Precise Bucketing Strategy:** An insufficient number of buckets can lead to excessive data volume in a single bucket, causing read amplification in RocksDB. 
* **Maximize Column Pruning Benefits:** Business SQL queries should explicitly specify the required columns to avoid selecting all fields. This is particularly important in scenarios involving log wide tables and dimension table joins, allowing Fluss to fully leverage its I/O savings advantages. 
* **Phased Migration:** There is no need to replace the entire traditional pipeline at once. Start by replacing large-state two-stream joins with Delta Joins, then gradually expand to Partial Update wide tables and lake-stream integration. Each step should deliver independent, quantifiable benefits, and should be promoted broadly only after its effectiveness has been verified.

## Future Roadmap

![](assets/taobao_realtime_decisions/future1.png)

In the future, the overall data architecture will gradually unify computational logic through Flink SQL, evolve into a unified lake-stream storage foundation based on Fluss and Paimon, and build a unified query acceleration layer leveraging StarRocks.
The ultimate goal is to achieve "one codebase, one dataset, and one metric definition," serving both real-time applications and offline analytics simultaneously, thereby thoroughly resolving data inconsistencies and high maintenance costs caused by the separation of stream and batch processing.

![](assets/taobao_realtime_decisions/future2.png)
