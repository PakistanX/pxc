from pathlib import Path

from pxc.lib.runtime import ActivityRuntime
from pxc.lib.tests.runtime.utils import create_manifest, make_activity_runtime


class TestReportHostFunctions:
    """Tests for report-* host functions on ActivityRuntime."""

    def _make_runtime(self, tmp_path: Path) -> ActivityRuntime:
        manifest = create_manifest(capabilities={"grading": {}})
        return make_activity_runtime(tmp_path, manifest)

    def test_report_completed(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        assert rt.report_completed() is True

    def test_report_passed_with_score(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        assert rt.report_passed(0.85) is True

    def test_report_passed_without_score(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        assert rt.report_passed(None) is True

    def test_report_failed_with_score(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        assert rt.report_failed(0.3) is True

    def test_report_failed_without_score(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        assert rt.report_failed(None) is True

    def test_report_progressed(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        assert rt.report_progressed(0.5) is True

    def test_report_scored(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        assert rt.report_scored(0.75) is True

    def test_report_scored_buffers_grade_event(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        rt.report_scored(0.75)
        grades = rt.clear_pending_grades()
        assert grades == [{"event_type": "grade", "payload": {"value": 0.75, "max_value": 1.0}}]
        # Buffer is drained by clear_pending_grades()
        assert rt.clear_pending_grades() == []

    def test_report_passed_without_score_defaults_to_full_value(
        self, tmp_path: Path
    ) -> None:
        rt = self._make_runtime(tmp_path)
        rt.report_passed(None)
        assert rt.clear_pending_grades() == [
            {"event_type": "grade", "payload": {"value": 1.0, "max_value": 1.0}}
        ]

    def test_report_failed_without_score_defaults_to_zero_value(
        self, tmp_path: Path
    ) -> None:
        rt = self._make_runtime(tmp_path)
        rt.report_failed(None)
        assert rt.clear_pending_grades() == [
            {"event_type": "grade", "payload": {"value": 0.0, "max_value": 1.0}}
        ]

    def test_report_completed_buffers_completion_event(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        rt.report_completed()
        assert rt.clear_pending_grades() == [
            {"event_type": "completion", "payload": {"completion": 1.0}}
        ]

    def test_report_progressed_buffers_completion_event(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        rt.report_progressed(0.4)
        assert rt.clear_pending_grades() == [
            {"event_type": "completion", "payload": {"completion": 0.4}}
        ]

    def test_report_functions_registered(self, tmp_path: Path) -> None:
        rt = self._make_runtime(tmp_path)
        grading = rt.host_functions()["grading"]
        for name in [
            "report-completed",
            "report-passed",
            "report-failed",
            "report-progressed",
            "report-scored",
        ]:
            assert name in grading, f"{name} not in grading interface"
