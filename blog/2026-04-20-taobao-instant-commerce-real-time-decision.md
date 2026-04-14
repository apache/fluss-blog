---
slug: taobao-instant-commerce-real-time-decision
title: "Taobao Real-Time Decisions at Scale with Fluss"
sidebar_label: "Taobao Instant Commerce: Real-Time Decisions at Scale with Fluss"
authors: [jark]
---

In autumn 2025, the sensational social media phenomenon of "The First Cup of Milk Tea in Autumn" swept through online platforms once again. 
With a simple tap on their screens, consumers had their beverages delivered within 30 minutes. 
This seemingly effortless moment reflects how Taobao Instant Commerce has evolved from a single-category food delivery service into a high-frequency core business covering all scenarios—including fresh produce, consumer electronics (3C), and beauty products.
Its business model is now driven by a dual engine: "Daily High-Frequency Consumption" and "Event-Driven Peak Bursts." 
In daily scenarios, activity windows are compressed to the minute level, requiring real-time responsiveness for millions of SKUs. 
During promotional peaks, traffic and orders surge exponentially.

Under this extreme pace, "real-time" has become the lifeline for operational decision-making, algorithm iteration, and quality monitoring:
* **Operations:** Refresh conversion rates and funnels within 30 seconds. 
* **Algorithms:** Require order prediction models to iterate at minute-level granularity. 
* **Quality Assurance:** Demands second-level visibility for gray-release discrepancies and instant alerting for anomalies.

The traditional data pipeline supporting this high-real-time system had long operated on an architecture comprising Alibaba’s Kafka message queue, along with Flink, Paimon, and StarRocks. 
However, as business scale continued to expand, three core contradictions became increasingly prominent: expanding state sizes for dimension tables, complex wide-table joins, and high resource consumption for lake-warehouse synchronization. 
These challenges even created an "impossible triangle" of latency, consistency, and cost-efficiency.

With the introduction of Fluss, these pain points were systematically resolved through the synergistic implementation of its key features: Delta Join, Partial Update, Streaming & Lakehouse Unification, Column Pruning, and Auto-Increment Columns. This transformation has fundamentally reshaped the architectural paradigm for real-time decision-making data pipelines.

<!-- truncate -->

## The "Impossible Triangle" Dilemma: Business Pain Points & Technical Challenges

The real-time data system of Taobao Instant Commerce must stably process ultra-large-scale, high-concurrency real-time data streams. 
It is also required to build real-time wide tables across multiple business domains and support core pipelines such as the real-time association of page view streams with order streams, as well as gray-scale monitoring. 
This imposes extreme requirements on latency, consistency, cost-efficiency, and system scalability.

However, under the traditional technology stack, the challenges across these four dimensions are deeply intertwined, ultimately forming a trilemma of latency, consistency, and cost-efficiency, where all three cannot be simultaneously optimized.

The root cause lies in the stream-batch separation at the storage layer: Kafka serving as the message queue, represents the "stream" abstraction, while Paimon, as the lakehouse format, represents the "batch" abstraction. 
Bridging these two relies heavily on numerous Flink ETL jobs acting as a "glue layer." 
Each additional layer of glue compounds latency, increases costs, and heightens the risk to data consistency.

### Four Core Business Issues
![](assets/taobao_realtime_decisions/issues.png)

### Three Core Pain Points of the Traditional Tech Stack
The traditional pipeline based on Kafka, Flink and Paimon exposed three critical pain points under Taobao Instant Commerce’s massive scale, high concurrency, and strict real-time requirements. 
These issues became the core focus areas for the subsequent Fluss implementation: 
* **Surging Memory Pressure from Dual-Stream Joins:** Kafka lacks native support for dimension table lookups. Consequently, order information had to be fully loaded into Flink State. During promotional events, over 100 million orders caused the state size of single jobs to surge to hundreds of GBs, leading to Checkpoint timeouts and frequent task failures.
* **"Explosive Tree" Complexity in Wide Table Construction:** The product-store analysis wide table depended on 5+ upstream systems. Using Kafka required writing to a new Topic after every Join operation. This resulted in an overly complex pipeline with extremely high operational and maintenance costs. 
* **Core Resource Drain from Lakehouse Synchronization:** Each table synced to Paimon required maintaining an independent Flink consumption job. During peak events, dozens of these "data transfer" jobs ran simultaneously, competing with core computing tasks for resources and causing overall performance degradation.

![](assets/taobao_realtime_decisions/arch.png)

### Architecture Selection Logic: From "Compute-Layer Stitching" to "Storage-Layer Unification"

Guided by the "impossible triangle" dilemma described above, we established a core principle for our technology selection: the breakthrough lies not in the compute layer, but in the storage layer. 
The traditional architecture, relying on the combination of Kafka, Flink and Paimon as the open table format, was essentially a "stitched" model characterized by stream-batch separation. 
As the compute engine, Flink was forced to assume numerous "glue" responsibilities: maintaining TB-scale State, scheduling dozens of data transfer jobs, and handling memory bloat from dual-stream joins. 
This not only drove up resource costs but also made data consistency difficult to guarantee.

Fluss’s design philosophy directly addresses this pain point through Stream-Batch Unification at the storage layer. 
It is not merely another message queue; rather, it converges streaming consumption and batch querying into a single distributed storage kernel. 
Streaming and batch operations require no data replication, no format conversion, and no additional ETL jobs for data movement. 
This fundamental shift in underlying architecture directly eliminates the three primary sources of latency, cost, and consistency risks inherent in traditional pipelines, providing a unified foundation for the implementation of subsequent core features.

## Fluss Core Scenario Implementation
Taobao Instant Commerce has designed a three-layer overall architecture and a feature-scenario matrix by leveraging Fluss’s five core features tailored to business needs. Establishing Fluss as the unified data foundation for real-time decision-making, this architecture integrates the full pipeline—from data ingestion and stream-batch processing to lakehouse storage and service delivery—precisely resolving scenario-specific pain points.

### Three-Layer Overall Architecture

![](assets/taobao_realtime_decisions/3_layer_arch.png)
The real-time data system of Taobao Instant Commerce, powered by Fluss, is structured into three layers: the Data Source Layer, the Fluss Storage & Compute Layer, and the Business Service Layer. Built on the core philosophy of Stream-Batch Unification, this architecture enables "Write Once, Read Anywhere" data reuse, completely eliminating the stream-batch separation and glue-layer ETL jobs inherent in traditional pipelines.
* **Data Source Layer:** Integrates all business data sources—including order streams, visit streams, product dimension tables, and inventory/price streams—and uniformly writes them into Fluss’s Log Tables or KV Tables, adapting to the specific ingestion characteristics of each data source. 
* **Fluss Storage & Compute Layer:** As the core layer, it achieves unified data storage via Fluss’s Log/KV Tables. It leverages features like Delta Join, Partial Update, and Streaming-Lakehouse Unification (Auto-Tiering) to handle real-time computation, multi-table joins, wide table construction, and lakehouse synchronization. Crucially, it provides stateless computing support for Flink, significantly reducing state management overhead. 
* **Business Service Layer:** Leveraging a unified data view from both Fluss and lakehouse storage (Paimon), this layer delivers data services to operational real-time dashboards, algorithmic order prediction models, gray-scale monitoring systems, and product-store analysis systems, enabling second-level decision support.

### Five Core Scenarios and Feature Combination Matrix

![](assets/taobao_realtime_decisions/matrix1.png)
![](assets/taobao_realtime_decisions/matrix2.png)

During the introduction of Fluss into Taobao Instant Commerce, we conducted initial explorations and practices. 
Beyond pilot validations of individual features, we focused on architectural adjustments and engineering adaptations across five core scenarios, accumulating valuable feedback from production environments. 
This article outlines the implementation details and preliminary results of these scenarios, aiming to provide reference insights for the community.

## Scenario 1: Real-Time Conversion Rate & Order Attribution — Solving Dual-Stream Join State Bloat with Delta Join

Conversion Rate (defined as the ratio of purchasing users to visiting users) is a core metric for measuring conversion efficiency in Taobao Instant Commerce. 
Its calculation relies on the real-time join of user visit streams with order streams, thereby directly enabling second-level operational decision-making.

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
To address the pain points of traditional architectures, our solution upgrades the conventional Flink dual-stream join to a Delta Join. This approach offloads the full volume of dual-stream data from Flink State to Fluss KV Tables (backed by RocksDB). By implementing bidirectional Prefix Lookup—where incoming records from either stream trigger a lookup in the opposite KV Table—we achieve a near-stateless dual-stream join. Furthermore, query performance is enhanced through MurmurHash-based bucket routing and column pruning. 
* **Dual KV Table Ingestion with Composite Keys:** The real-time order stream is written to a Fluss KV Table with PRIMARY KEY (user_id, ds, order_id) and bucket.key = 'user_id'. Simultaneously, real-time traffic visit logs are written to a Fluss KV Table with PRIMARY KEY (user_id, ds) and bucket.key = 'user_id'. Both tables utilize a composite primary key design where the join key (user_id) serves as the bucket.key and is a strict prefix of the primary key, enabling efficient Prefix Lookup operations. 
* **Stateless Bidirectional Join via Delta Join Operator:** Leveraging the Delta Join operator in Flink 2.1+, we implement bidirectional association: incoming orders trigger lookups in the visit log table, and incoming visits trigger lookups in the order table. Flink calculates the target bucketId using MurmurHash(bucket.key) to route RPC requests precisely to the single Fluss TabletServer holding that specific bucket’s RocksDB instance. This eliminates the need for broadcast scans or full-table scans. The Flink operator itself retains only minimal transient state (for asynchronous lookup queues), completely removing dependency on large-scale Join State. 
* **Real-Time Attribution & Lakehouse Sync:** The joined results are written to a Fluss wide table and automatically synchronized to Paimon via the Streaming-Lakehouse Unification mechanism. The data is finally served to StarRocks and real-time BI dashboards, achieving metric refresh latency within 30 seconds.

### Core DDL and Join SQL

```sql
-- Note: ${xxx} represents environment-specific parameters. 
-- Actual deployment values should be evaluated based on cluster scale and data volume.

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
CREATE TABLE `fluss_catalog`.`db`.`log_page_ord_detail_ri`
(
    `user_id`       STRING COMMENT 'User ID',
    `order_id`      STRING COMMENT 'Order ID',
    `first_page_time` STRING COMMENT 'First Visit Time',
    `order_time`    STRING COMMENT 'Order Placement Time',
    `pv`            BIGINT COMMENT 'Page Views (Visit Count)',
    `pay_amt`       STRING COMMENT 'Payment Amount',
    `is_matched`    STRING COMMENT 'Match Status',
    `ds`            STRING COMMENT 'Date Partition',
   PRIMARY KEY (user_id, order_id, ds) NOT ENFORCED
)
COMMENT 'Attribution Result Table'
PARTITIONED BY (ds)
WITH (
    'bucket.key' = 'user_id,order_id',
    'bucket.num' = '${BUCKET_NUM}',
    'table.auto-partition.enabled' = 'true',
    'table.auto-partition.key' = 'ds',
    'table.datalake.enabled' = 'true', -- Enable Streaming-Lakehouse Unification
    'table.datalake.freshness' = '3min' -- Controls Lakehouse Table Freshness
);
```
Subsequently, the Lakehouse Tiering Service continuously tiers data from Fluss to Paimon. 
The parameter table.datalake.freshness controls the frequency at which Fluss writes data to the Paimon table. 
By default, the data freshness is set to 3 minutes. 

The implementation of the Delta Join is as follows:

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
        ON l.user_id = o.user_id AND l.ds = o.ds
```

Fluss supports two TTL (Time-To-Live) mechanisms: 
* **Changelog Expiration:** Controlled by table.log.ttl (default: 7 days). 
* **Data Partition Expiration:** Controlled by table.auto-partition.num-retention (default: 7 partitions).

### Quantification of Implementation Results
The Fluss Delta Join solution enables stateless dimension table joins, completely resolving the State bloat issue and delivering order-of-magnitude improvements in core metrics:

![](assets/taobao_realtime_decisions/results.png)

## Scenario 2: Real-Time Product-Store Wide Table — Efficient Column-Level Updates via Partial Update

In Taobao Instant Commerce’s traffic operations ecosystem, the Real-time Product-Store Wide Table stands as the most critical data asset within the traffic domain. 
This wide table must aggregate four core behavioral streams—impressions, clicks, visits, and orders—in real time, outputting key metrics (such as Impression UV/PV, Click UV/PV, Visit UV/PV, Order UV, and GMV) across both "Product" and "Store" dimensions. It directly powers real-time traffic dashboards, ROI analysis, algorithmic feature engineering, and decision-making in activity war rooms.

However, facing the immense pressure of behavior log traffic driven by ultra-large scale and extreme concurrency, traditional real-time aggregation models based on "Multi-stream Joins" face severe challenges, including significant State bloat, high pipeline coupling, and poor fault tolerance.

Fluss addresses these issues by leveraging Partial Update. It refactors the complex "multi-stream real-time join aggregation" into a streamlined architecture of "independent multi-stream writes with automatic server-side column-level merging." This transformation simplifies the real-time wide table construction pipeline and delivers a leap in performance.

### Pain Points of Traditional Solutions
![](assets/taobao_realtime_decisions/painpoints2.png)

The legacy solution constructed the wide table using Kafka Multi-stream Joins, resulting in a complex fan-in architecture. Its core pain points are as follows:
* **Full-Row Write I/O Waste:** Even if only a single behavior metric (e.g., "clicks" or "impressions") is updated, the system must write all 100+ columns of the full row. This causes severe redundancy in both network and storage I/O. 
* **High Operational Complexity:** The architecture resembles an "explosive tree" structure, requiring the maintenance of N upstream jobs and M join jobs. Adding a new field necessitates modifications across multiple jobs, significantly increasing operational overhead. 
* **Latency Coupling (Straggler Problem):** The write latency of the wide table is determined by the slowest upstream stream. A delay in any single data stream causes the entire row update to be delayed, leading to inconsistent real-time visibility. 
* **State Bloat and Lack of Hot Updates:** To wait for data from different behavior streams to match for conversion rate calculations, Flink must cache massive amounts of intermediate state locally. This leads to TB-scale state bloat, Checkpoint timeouts, and risks of Out-of-Memory (OOM) errors. Furthermore, due to the tightly coupled Join logic, the system cannot support hot schema updates during live promotional events; any scaling or model changes require service downtime and data reprocessing.

### Architecture Based on Fluss Partial Update
![](assets/taobao_realtime_decisions/solution2.png)

To address the aforementioned pain points, our solution utilizes Fluss KV Tables as the unified storage for a multi-dimensional wide table (spanning Product and Store dimensions). By leveraging Partial Update, we achieve column-level updates that completely decouple the ingestion of diverse behavior streams—such as impressions, clicks, visits, and orders. Each Flink job is responsible solely for aggregating its specific behavioral metrics and writing to the target columns, eliminating the need for complex multi-stream joins. The field-level merging is automatically handled by the RowMerger on the Fluss server side. The core architectural workflow is as follows: 
* **Independent Aggregation & Ingestion of Multiple Streams:** Five or more upstream behavior streams (impressions, clicks, visits, add-to-cart, orders) run as independent Flink jobs. Each job consumes only a single type of behavior log, pre-aggregates data by "Product" or "Store" dimension, and writes exclusively to the corresponding metric columns in the wide table. This approach thoroughly eliminates inter-stream dependencies. 
* **Server-Side Intelligent Column-Level Merging:** Fluss leverages the Partial Update feature, utilizing BitSet bitmap technology to identify target columns in write requests. Within the storage engine, only the target columns are read and updated (via accumulation or overwrite), while non-target columns retain their historical values in RocksDB. This avoids transmitting redundant data over the network or in memory, achieving microsecond-level merging. 
* **Streaming-Lakehouse Unification with Auto-Tiering:** The merged, up-to-date wide table data provides low-latency point queries and streaming consumption capabilities in real-time. Simultaneously, the Auto-Tiering mechanism asynchronously tiers data into the Paimon lakehouse. This supports offline T+1 validation, historical backtracking, and AI model training without requiring additional ETL development for data movement. 
* **Online Schema Evolution:** When new statistical metrics are required, business teams simply execute an ALTER TABLE ADD COLUMN DDL statement and deploy a new write job for that specific column. This takes effect immediately without downtime or restarting existing jobs (e.g., for impressions or orders), enabling agile iteration even during peak promotional events.

### Core DDL and Per-Job Write Implementation

```sql
CREATE TABLE shop_stat_wide (
                                shop_id      BIGINT NOT NULL,
                                stat_date    STRING NOT NULL,
                                stat_hour    STRING NOT NULL,
                                exp_cnt      BIGINT,   -- Exposure Count
                                page_cnt     BIGINT,   -- Page View Count
                                PRIMARY KEY (shop_id, stat_date, stat_hour) NOT ENFORCED
) WITH (
      'bucket.num' = '${BUCKET_NUM}',
      'bucket.key' = 'shop_id'
      );

-- Write Exposure Data
INSERT INTO shop_stat_wide (shop_id, stat_date, stat_hour, exp_cnt)
SELECT
    shop_id,
    stat_date,
    stat_hour,
    SUM(exp_cnt) AS exp_cnt
FROM exposure_log
GROUP BY shop_id, stat_date, stat_hour;

-- Write Visit Data
INSERT INTO shop_stat_wide (shop_id, stat_date, stat_hour, page_cnt)
SELECT
    shop_id,
    stat_date,
    stat_hour,
    SUM(page_cnt) AS page_cnt
FROM page_log
GROUP BY shop_id, stat_date, stat_hour;
```

### Quantification of Implementation Results
The Fluss Partial Update solution enables column-level updates and decoupled writes for wide tables, delivering significant improvements in core metrics while reducing operational costs.

![](assets/taobao_realtime_decisions/results2.png)

## Scenario 3: Real-Time Order Estimation — Efficient Data Fusion via Fluss KV Lake-Stream Unification
Real-time order forecasting serves as a critical support pillar in Taobao Instant Commerce’s algorithmic decision-making framework. 
During promotional events, the system iterates the prediction model every minute to accurately project the total daily Gross Merchandise Volume (GMV), thereby enabling dynamic adjustments to subsidy strategies and inventory allocation.
This scenario imposes extreme challenges on the data pipeline: model inputs must deeply integrate real-time cumulative order streams (high-frequency incremental data) with historical baseline data from corresponding periods (massive static data), demanding exceptionally high standards for both data consistency and low latency.

![](assets/taobao_realtime_decisions/scenario3.png)

### Architecture Based on Fluss Lake-Stream Unification
![](assets/taobao_realtime_decisions/arch3.png)

The current implementation leverages Fluss KV Tables as a unified storage layer for both streaming and batch processing. By integrating Streaming-Lakehouse Unification, it enables automated synchronization to the data lake. Since both streaming and batch operations rely on the same KV Table, data consistency is inherently guaranteed. This approach eliminates the need for independent data migration jobs, ensuring low-latency synchronization of prediction results.Core Architecture Workflow:
* **Real-time Accumulation:** The real-time order stream is written into the Fluss KV Table, enabling the calculation of rolling cumulative order counts on a per-minute basis via stream reads. 
* **Efficient Stream-Batch Fusion:** A Flink UDF directly reads both real-time data (via stream read) and historical baseline data (via batch read / Snapshot Lookup) from the Fluss KV Table, achieving efficient fusion of streaming and batch data. 
* **Low-Latency Lake Sync:** Model prediction results are written back to the Fluss KV Table. With automatic Tiering enabled, these results are synchronized to Paimon with low latency (with configurable snapshot intervals). 
* **Unified Data Consistency:** Downstream algorithm models and operational dashboards read real-time prediction results from the Fluss KV Table and historical prediction results from Paimon, ensuring end-to-end data consistency across the entire pipeline.

### Core DDL and Write Implementation

```sql
-- Note: ${xxx} represents environment-specific parameters. 
-- Actual deployment values should be evaluated based on cluster scale and data volume.

-- 1. Real-time Order Minute-Accumulation Stream
CREATE TABLE `fluss_catalog`.`db`.`order_dtm`
(
    `ds` STRING COMMENT 'Day Partition',
    `mm` STRING COMMENT 'Minute',
    `order_source` STRING COMMENT 'Order Source',
    `order_cnt` BIGINT COMMENT 'Order Count',
    PRIMARY KEY (ds, mm, order_source) NOT ENFORCED
)
    COMMENT 'Real-time Order Minute-Accumulation Stream'
PARTITIONED BY (ds)
WITH (
  'bucket.key' = 'mm,order_source',
  'bucket.num' = '${BUCKET_NUM}',
  'table.auto-partition.enabled' = 'true',
  'table.auto-partition.time-unit' = 'day',
  'table.auto-partition.key' = 'ds',
  'table.auto-partition.num-precreate' = '0', -- Number of future partitions to pre-create.
  'table.auto-partition.num-retention' = '2', -- Retain the last N partitions; automatically delete older ones.
  'table.replication.factor' = '${REPLICATION_FACTOR}',
  'table.log.arrow.compression.type' = 'zstd'
);

-- 2. Order Forecast Stream (Fluss Streaming-Lakehouse Unification)
CREATE TABLE `fluss_catalog`.`db`.`order_forecast_mm`
(
    `ds` STRING COMMENT 'Date Partition (Format: yyyymmdd)',
    `mm` STRING COMMENT 'Minute (Format: HH:mm or HHmm)',
    `order_source` STRING COMMENT 'Order Source',
    `cumulative_order_cnt` BIGINT COMMENT 'Cumulative Order Count up to the current minute',
    `forecast_daily_order_cnt` STRING COMMENT 'Predicted Total Daily Order Volume (24h) based on historical ratios',
    PRIMARY KEY (ds, mm, order_source) NOT ENFORCED
)
    COMMENT 'Order Forecast Stream'
PARTITIONED BY (ds)
WITH (
  'bucket.key' = 'mm,order_source',
  'bucket.num' = '${BUCKET_NUM}',
  'table.auto-partition.enabled' = 'true',
  'table.auto-partition.time-unit' = 'day',
  'table.auto-partition.key' = 'ds',
  'table.auto-partition.num-precreate' = '0',
  'table.auto-partition.num-retention' = '2',
  'table.replication.factor' = '${REPLICATION_FACTOR}',
  'table.log.arrow.compression.type' = 'zstd',
  'table.datalake.enabled' = 'true', -- Enable Streaming-Lakehouse Unification
  'table.datalake.freshness' = '30s' -- Controls Lakehouse Table Freshness
);

-- 3. Real-time Incremental & Offline Feature Fusion: 
-- Uses Flink Temporal Join to associate the Fluss real-time stream with the Paimon historical baseline table, 
-- and performs prediction calculations via a UDF.
CREATE TEMPORARY FUNCTION predict_hour_gmv AS 'com.example.flink.udf.FutureHourlyForecastUDF';

CREATE TEMPORARY VIEW trd_item_order AS
SELECT
    ds,
    mm,
    order_source,
    order_cnt,
    PROCTIME() AS proc_time
FROM `fluss_catalog`.`db`.`order_dtm`;

INSERT INTO `fluss_catalog`.`db`.`order_forecast_mm`
SELECT
    t1.ds,
    t1.mm,
    t1.order_source,
    t1.order_cnt AS cumulative_order_cnt,
    predict_hour_gmv(
            COALESCE(t1.order_cnt, 0),
            t1.mm,
            t2.minute_ratio_feat
    ) AS forecast_hour_order_cnt
FROM
    trd_item_order t1
        LEFT JOIN paimon_catalog.db.order_mm_his_str /*+ OPTIONS(
    'scan.partitions' = 'max_pt()',
    'lookup.dynamic-partition.refresh-interval' = '1 h'
) */
FOR SYSTEM_TIME AS OF t1.proc_time AS t2 ON t1.order_source = t2.channel_id;
```

### Quantification of Implementation Results
The Fluss KV Streaming-Lakehouse Unification solution achieves unified source integration for streaming and batch data, eliminating independent data migration jobs and delivering significant improvements in core metrics:

![](assets/taobao_realtime_decisions/results3.png)

## Scenario 4: Gray-Scale Monitoring — Efficient Log Processing via Log Table and Column Pruning
In the context of Taobao Instant Commerce’s high-frequency iteration cycle, frontend telemetry data—covering the full user journey from app launch, site entry, impressions, traffic redirection, store visits, cart additions, orders, to fulfillment—serves as the core basis for evaluating release quality, monitoring marketing effectiveness, and optimizing search and recommendation strategies. To mitigate release risks, canary releases have become the standard procedure, with canary monitoring acting as the critical "safety valve." This process aims to detect data collection anomalies or business logic defects within seconds by real-time analysis of discrepancies between canary traffic and baseline traffic. However, facing TB-scale log throughput and millisecond-level alerting requirements, the traditional "Kafka + Flink" architecture has gradually revealed bottlenecks such as severe I/O waste, redundant pipelines, and data silos across multiple sources.

Fluss has refactored the data foundation for canary monitoring by leveraging: 
* High-throughput writes via Log Tables; 
* Server-side column pruning for I/O optimization; 
* Automatic archiving through Streaming-Lakehouse Unification.

This transformation upgrades the architecture from "reactive firefighting" to "proactive governance."
### Pain Points of Traditional Solutions
![](assets/taobao_realtime_decisions/painpoints3.png)

The legacy architecture utilized Kafka as the message queue, Flink for real-time consumption and computation, and Paimon for storing detailed data. However, as data volumes surged and business complexity increased, this architecture exposed several core pain points:

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

### Core DDL and Write Implementation

```sql
-- Note: ${xxx} represents environment-specific parameters. 
-- Actual deployment values should be evaluated based on cluster scale and data volume.

CREATE TABLE `fluss_catalog`.`db`.`log_page_ri`
(
    `col1` STRING,
    `col2` STRING,
    `col3` STRING,
    `col4` STRING
    -- ....... Intermediate fields omitted
    ,ds STRING
)
    COMMENT 'Page View Log Stream'
PARTITIONED BY (ds) -- Partition key defined above
WITH (
  'bucket.num' = '${BUCKET_NUM}',
  'table.auto-partition.enabled' = 'true',
  'table.auto-partition.time-unit' = 'day',
  'table.auto-partition.key' = 'ds',
  'table.auto-partition.num-precreate' = '0', 
  'table.auto-partition.num-retention' = '1',
  'table.log.ttl' = '${LOG_TTL}',
  'table.replication.factor'='${REPLICATION_FACTOR}',
  'table.log.arrow.compression.type' = 'zstd',
  'table.datalake.enabled' = 'true', -- Enable Streaming-Lakehouse Unification
  'table.datalake.freshness' = '3min' -- Control lake table data freshness
)
;

-- Monitoring Query (Reads only 30 core columns to trigger server-side column pruning)
INSERT INTO `fluss_catalog`.`db`.ads_gray_monitoring_ri /*+ OPTIONS('client.writer.enable-idempotence'='false') */
SELECT
    col1,
    col2,
    col3,
    col4,
    -- ......... Intermediate fields omitted
    ds
FROM `fluss-ali-log`.`db`.`log_page_ri`
WHERE KEYVALUE(`args`, ',', '=', 'release_type') = 'grey' -- Canary release flag
;

-- Flink Cube Aggregation
INSERT INTO `fluss_catalog`.`db`.ads_gray_monitoring_permm_ri /*+ OPTIONS('client.writer.enable-idempotence'='false') */
SELECT
    col1,
    col2,
    col3,
    col4,
    count(*) AS pv,
-- ......... Intermediate fields omitted
```

### Quantification of Implementation Results
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
* **Hologres Lookup Hotspots and Network Bottlenecks:** Flink issued massive volumes of RPC requests to Hologres. Under high concurrency, this led to data skew and hotspots, causing Lookup latency to degrade to the second level. 
* **Flink State Bloat and Checkpoint Failures:** Flink UDFs were required to maintain TB-scale Bitmap State. This resulted in excessively long Checkpoint durations (>10 minutes), frequent timeouts, and poor job stability. 
* **Paimon Synchronization Latency:** Paimon Compaction introduced minute-level latency, resulting in insufficient data freshness for downstream StarRocks Materialized Views (SR MVs). This failed to meet the requirements for second-level monitoring.

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
### Core DDL and Write Implementation

#### User Mapping Table (with Auto-Increment Column Enabled)

```sql
-- Note: ${xxx} represents environment-specific parameters. 
-- Actual deployment values should be evaluated based on cluster scale and data volume.

CREATE TABLE `fluss_catalog`.`db`.`user_mapping_table` (
  user_id BIGINT COMMENT 'Original User ID',
  uid_int64 BIGINT COMMENT 'Auto-incremented Globally Unique Integer ID', 
  update_time TIMESTAMP(3) COMMENT 'Update Time',
  PRIMARY KEY (user_id) NOT ENFORCED
) WITH (
  'bucket.key' = 'user_id',
  'bucket.num' = '${BUCKET_NUM}',
  'auto-increment.fields' = 'uid_int64', -- Enable auto-increment column
  'table.log.arrow.compression.type' = 'zstd'
);
```
#### New User Discovery and Mapping Ingestion
```sql
INSERT INTO `fluss_catalog`.`db`.`user_mapping_table` (user_id) 
SELECT /*+ REPLICATED_SHUFFLE_HASH(t2) */ 
  t1.user_id
FROM `fluss_catalog`.`db`.`log_exp_ri` t1
LEFT JOIN `fluss_catalog`.`db`.`user_mapping_table` 
 /*+ OPTIONS(
    'lookup.insert-if-not-exists' = 'true',
    'lookup.cache' = 'PARTIAL',
    'lookup.partial-cache.max-rows' = '500000',
    'lookup.partial-cache.expire-after-write' = '1h',
    'lookup.partial-cache.cache-missing-key' = 'false'
) */
FOR SYSTEM_TIME AS OF PROCTIME() AS t2 
ON t1.user_id = t2.user_id
GROUP BY t1.user_id;
```

#### Implementation of Solution A: Fluss Agg Table + Flink Global Merge
Core Idea: Leverage the Fluss Aggregation Table to perform partial Bitmap merging on the server side, while Flink only consumes the aggregated results to execute the global merge.

**Fluss DDL (Agg Table)**
```sql
-- Note: ${xxx} represents environment-specific parameters. 
-- Actual deployment values should be evaluated based on cluster scale and data volume.
CREATE TABLE IF NOT EXISTS `fluss_catalog`.`db`.`ads_uv_agg` (
    ds STRING COMMENT 'Date partition yyyyMMdd',
    hh STRING COMMENT 'Hour HH',
    mm STRING COMMENT 'Minute mm',
    shard_id INT COMMENT 'Shard ID',
    uv_bitmap BYTES COMMENT 'Minute-level user bitmap',
    PRIMARY KEY (ds, hh, mm, shard_id) NOT ENFORCED
) 
PARTITIONED BY (ds)
WITH (
    'bucket.key' = 'shard_id',
    'bucket.num' = '${BUCKET_NUM}',
    'table.merge-engine' = 'aggregation',  -- Enable aggregation engine; otherwise, Bytes fields cannot be automatically merged
    'fields.uv_bitmap.agg' = 'rbm32', -- Specify that the Bytes field uses the rbm32 algorithm for Union aggregation
    'table.auto-partition.enabled' = 'true',
    'table.auto-partition.time-unit' = 'day',
    'table.auto-partition.key' = 'ds'
);
```
**Fluss DML (Agg Table)**
```sql
-- Note: N is a power of 2 and should be dynamically configured based on cluster scale.
INSERT INTO fluss_catalog.db.ads_uv_agg
SELECT
  t1.ds 
  ,t1.hh 
  ,t1.mm 
  ,CAST(t2.uid_int64 % N AS INT) AS shard_id
  ,BITMAP_TO_BYTES(BITMAP_BUILD_AGG(CAST((t2.uid_int64 / N) AS INT))) AS uv_bitmap
FROM `fluss_catalog`.`db`.`log_exp_ri` t1
LEFT JOIN `fluss_catalog`.`db`.`user_mapping` 
  /*+ OPTIONS('lookup.cache' = 'PARTIAL','lookup.partial-cache.max-rows' = '500000') */
  FOR SYSTEM_TIME AS OF PROCTIME() AS t2 
ON t1.user_id = t2.user_id
GROUP BY t1.ds, t1.hh, t1.mm, CAST(t2.uid_int64 % N AS INT)
;
```

#### Implementation of Solution A: Fluss Agg Table + Flink Global Merge
Core Idea: Fluss serves as a high-quality data pipeline, synchronizing data to Paimon via Auto Tiering. It then leverages StarRocks' powerful OLAP engine to perform final deduplication.

**Fluss DDL (Log/KV Table with Tiering):**
```sql
CREATE TABLE fluss_catalog.db.ads_uv_detail (
    ds STRING,
    -- ....... Intermediate fields omitted
    shard_id INT,
    uid_int32 INT,
    PRIMARY KEY (ds, shard_id, uid_int32) NOT ENFORCED
) WITH (
    'table.datalake.enabled' = 'true', -- Enable Streaming-Lakehouse Unification
    'table.datalake.freshness' = '10s' -- Second-level synchronization
);
```

**Fact Table Denormalization (Generating Shard ID and Bitmap Index)**
```sql
-- Note: N is a power of 2 and should be dynamically configured based on cluster scale.
INSERT INTO fluss_catalog.db.ads_uv_detail
SELECT
  t1.ds,
  -- ....... Intermediate fields omitted
  CAST(t2.uid_int64 % N AS INT) AS shard_id,      -- Shard ID, used for parallel aggregation
  CAST((t2.uid_int64 / N) AS INT) AS uid_int32   -- Compressed ID, used for Bitmap
FROM `fluss_catalog`.`db`.`log_exp_ri` t1
LEFT JOIN `fluss_catalog`.`db`.`user_mapping` 
  /*+ OPTIONS('lookup.cache' = 'PARTIAL','lookup.partial-cache.max-rows' = '500000','lookup.partial-cache.expire-after-access' = '2min') */
  FOR SYSTEM_TIME AS OF PROCTIME() AS t2 
ON t1.user_id = t2.user_id;
```

**Downstream StarRocks Precise Deduplication Query**
```sql
-- Note: ${xxx} in the text represents environment-specific parameters. Actual deployment requires evaluation based on cluster scale and data volume.
-- Create a materialized view to accelerate queries
CREATE MATERIALIZED VIEW mv_global_uv AS
SELECT 
  t.ds,
  SUM(t.rb_partial) as rbm_user_count -- Globally merge partial Bitmaps from each shard
FROM (
  SELECT 
    ds,
    shard_id, 
    BITMAP_UNION_COUNT(TO_BITMAP(uid_int32)) as rb_partial -- Partial Bitmap count
  FROM 
    paimon_catalog.db.ads_uv_detail
  WHERE 
    ds = '${date}'
  GROUP BY 
    ds, shard_id
) t
GROUP BY t.ds;
```

**Features: Decoupled architecture; StarRocks bears the computational load and supports flexible ad-hoc queries.**

### Quantification of Implementation Results
Compared to the legacy solution, both new approaches achieve significant optimizations, but with different focuses:
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
