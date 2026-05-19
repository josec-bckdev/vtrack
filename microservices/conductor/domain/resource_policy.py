from dataclasses import dataclass, field

from conductor.domain.ports import ContainerStats


@dataclass
class ResourceSummary:
    containers: list[ContainerStats]
    total_memory_mb: float
    total_cpu_percent: float


def evaluate_savings(stats: list[ContainerStats]) -> ResourceSummary:
    total_memory_mb = sum(s.memory_bytes for s in stats) / (1024 * 1024)
    total_cpu = sum(s.cpu_percent for s in stats)
    return ResourceSummary(
        containers=stats,
        total_memory_mb=total_memory_mb,
        total_cpu_percent=total_cpu,
    )


def should_stop_after_slot(
    summary: ResourceSummary,
    memory_threshold_mb: float = 256.0,
) -> bool:
    return summary.total_memory_mb >= memory_threshold_mb
