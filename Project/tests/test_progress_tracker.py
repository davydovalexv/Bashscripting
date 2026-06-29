from dv_agent.ui.progress_tracker import ProgressTracker, format_duration


def test_format_duration():
    assert format_duration(45) == "45 сек"
    assert format_duration(125) == "2 мин 5 сек"
    assert format_duration(3665) == "1 ч 1 мин"


def test_progress_tracker_eta():
    tracker = ProgressTracker(total=3, default_table_sec=100)
    tracker.on_table_start(1, "t1")
    tracker.on_table_done(1, "t1", 120)
    assert tracker.remaining_seconds(2) == 240  # 2 tables left × 120 avg
    line = tracker.status_line(2, 3, "t2", phase="start")
    assert "осталось" in line
    assert "прошло" in line
