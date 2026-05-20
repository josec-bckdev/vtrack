from prometheus_client import Counter, Gauge, Histogram

collection_total = Counter(
    "vtrack_collection_total",
    "Total collection run outcomes by slot and result",
    ["slot", "outcome"],
)

guardian_state = Gauge(
    "vtrack_guardian_state",
    "Current guardian state per slot — 1 means active, 0 means inactive",
    ["slot", "state"],
)

collection_datapoints = Histogram(
    "vtrack_collection_datapoints",
    "Datapoints collected per run",
    ["slot"],
    buckets=[10, 25, 50, 100, 250, 500, 1000, float("inf")],
)
