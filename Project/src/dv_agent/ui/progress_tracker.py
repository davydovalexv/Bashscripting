from __future__ import annotations

import time
from dataclasses import dataclass, field


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    if total < 60:
        return f"{total} сек"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} мин {secs} сек"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} ч {minutes} мин"


@dataclass
class ProgressTracker:
    """Оценка ETA по длительности уже обработанных таблиц."""

    total: int
    default_table_sec: float = 300.0
    started_at: float = field(default_factory=time.monotonic)
    table_durations: list[float] = field(default_factory=list)
    current_table: str | None = None
    current_started_at: float | None = None

    def on_table_start(self, current: int, name: str) -> None:
        self.current_table = name
        self.current_started_at = time.monotonic()

    def on_table_done(self, current: int, name: str, elapsed_sec: float) -> None:
        self.table_durations.append(elapsed_sec)
        self.current_table = None
        self.current_started_at = None

    def elapsed_total(self) -> float:
        return time.monotonic() - self.started_at

    def avg_table_seconds(self) -> float:
        if self.table_durations:
            return sum(self.table_durations) / len(self.table_durations)
        return self.default_table_sec

    def remaining_seconds(self, current: int) -> float:
        """Сколько секунд осталось с учётом текущей и следующих таблиц."""
        avg = self.avg_table_seconds()
        remaining_tables = self.total - current + 1
        return max(0.0, avg * remaining_tables)

    def status_line(self, current: int, total: int, name: str, *, phase: str) -> str:
        elapsed = format_duration(self.elapsed_total())
        if phase == "start":
            if self.table_durations:
                eta = format_duration(self.remaining_seconds(current))
                return (
                    f"Таблица {current}/{total}: {name} · "
                    f"прошло {elapsed} · осталось ~{eta}"
                )
            return (
                f"Таблица {current}/{total}: {name} · "
                f"прошло {elapsed} · осталось: оценка после 1-й таблицы"
            )

        # phase == "done"
        eta = "0 сек" if current >= total else f"~{format_duration(self.remaining_seconds(current + 1))}"
        return (
            f"Готово {current}/{total}: {name} "
            f"({format_duration(self.table_durations[-1])}) · "
            f"прошло {elapsed} · осталось {eta}"
        )

    def progress_fraction(self, current: int, *, done: bool) -> float:
        if done:
            return current / self.total
        # Во время обработки — доля завершённых таблиц
        return (current - 1) / self.total if current > 1 else 0.0
