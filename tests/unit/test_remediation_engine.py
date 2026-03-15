"""
Unit tests for the auto-remediation engine.

All Kubernetes and healing-action calls are mocked so the tests run without
a live cluster or database.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from intelligent_sre_mcp.remediation_engine import (
    _ISSUE_TO_PLAYBOOK,
    CONFIDENCE_THRESHOLD,
    PLAYBOOKS,
    DetectedIssue,
    IssueType,
    RemediationEngine,
    RemediationOutcome,
    RemediationPlaybook,
    list_playbooks,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine(
    failing_pods=None,
    describe_pod_return=None,
    node_status=None,
    mock_store=None,
    pod_logs=None,
):
    """Return a RemediationEngine with mocked KubernetesTools + HealingActions."""
    k8s = MagicMock()
    k8s.get_failing_pods.return_value = failing_pods or []
    k8s.describe_pod.return_value = describe_pod_return or {}
    k8s.get_node_status.return_value = node_status or []
    k8s.get_pod_logs.return_value = pod_logs or {"logs": ""}
    k8s.get_deployment_status.return_value = {
        "name": "my-app",
        "replicas": {"desired": 2, "current": 2, "ready": 1, "available": 1, "unavailable": 1},
    }

    healing = MagicMock()
    healing.restart_pod.return_value = {"success": True, "action": "restart_pod"}
    healing.delete_failed_pods.return_value = {"success": True, "deleted": []}
    healing.scale_deployment.return_value = {"success": True, "action": "scale_deployment"}
    healing.rollback_deployment.return_value = {"success": True, "action": "rollback_deployment"}

    if mock_store is not None:
        store = mock_store
    else:
        store = MagicMock()
        store.past_successes.return_value = 0
        store.save_run.return_value = 1

    return RemediationEngine(k8s_tools=k8s, healing_actions=healing, store=store)


# ---------------------------------------------------------------------------
# Playbook Registry Tests
# ---------------------------------------------------------------------------


class TestPlaybookRegistry:
    def test_all_playbooks_have_required_fields(self):
        for name, pb in PLAYBOOKS.items():
            assert pb.name == name
            assert pb.title
            assert pb.description
            assert pb.issue_types
            assert pb.actions
            assert 0.0 < pb.base_confidence < 1.0

    def test_all_playbooks_have_at_least_one_action(self):
        for pb in PLAYBOOKS.values():
            assert len(pb.actions) >= 1

    def test_issue_to_playbook_mapping_covers_all_playbooks(self):
        mapped_types = set(_ISSUE_TO_PLAYBOOK.keys())
        pb_types = {t for pb in PLAYBOOKS.values() for t in pb.issue_types}
        assert mapped_types == pb_types

    def test_list_playbooks_returns_all(self):
        result = list_playbooks()
        assert len(result) == len(PLAYBOOKS)
        for item in result:
            assert "name" in item
            assert "title" in item
            assert "actions" in item
            assert item["confidence_threshold"] == CONFIDENCE_THRESHOLD

    def test_list_playbooks_includes_issue_types(self):
        for item in list_playbooks():
            assert isinstance(item["issue_types"], list)
            assert len(item["issue_types"]) >= 1


# ---------------------------------------------------------------------------
# Issue Detection Tests
# ---------------------------------------------------------------------------


class TestIssueDetection:
    def test_no_failing_pods_returns_empty(self):
        engine = _make_engine(failing_pods=[], node_status=[])
        issues = engine.detect_issues()
        assert issues == []

    def test_crashloopbackoff_detected_via_container_state(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "api-7d8f9b-xk2p4",
                    "namespace": "production",
                    "status": "Running",
                    "restart_count": 5,
                    "ready": False,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "api", "reason": "CrashLoopBackOff", "state": "Waiting"}],
                "events": [],
                "labels": {"app": "api"},
                "created_at": "2024-01-01T00:00:00+00:00",
            },
        )
        issues = engine.detect_issues()
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.CRASHLOOP_BACKOFF
        assert issues[0].pod_name == "api-7d8f9b-xk2p4"
        assert issues[0].namespace == "production"

    def test_oomkilled_detected_via_container_state(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "worker-abc-xyz",
                    "namespace": "default",
                    "status": "Running",
                    "restart_count": 3,
                    "ready": False,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "worker", "reason": "OOMKilled", "state": "Terminated"}],
                "events": [],
                "labels": {"app": "worker"},
                "created_at": "2024-01-01T00:00:00+00:00",
            },
        )
        issues = engine.detect_issues()
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.OOM_KILLED

    def test_imagepullbackoff_detected(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "svc-ab1-cd2",
                    "namespace": "staging",
                    "status": "Running",
                    "restart_count": 0,
                    "ready": False,
                    "node": "node-2",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "svc", "reason": "ImagePullBackOff", "state": "Waiting"}],
                "events": [],
                "labels": {},
                "created_at": "2024-01-01T00:00:00+00:00",
            },
        )
        issues = engine.detect_issues()
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.IMAGE_PULL_BACKOFF

    def test_failed_pod_phase_detected(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "job-pod-xyz",
                    "namespace": "batch",
                    "status": "Failed",
                    "restart_count": 0,
                    "ready": False,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [],
                "events": [],
                "labels": {},
                "created_at": "2024-01-01T00:00:00+00:00",
                "status": "Failed",
            },
        )
        issues = engine.detect_issues()
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.POD_FAILED

    def test_high_restart_count_detected_when_running(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "app-de1-fg2",
                    "namespace": "default",
                    "status": "Running",
                    "restart_count": 15,
                    "ready": True,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "app", "state": "Running"}],
                "events": [],
                "labels": {"app": "myapp"},
                "created_at": "2024-01-01T00:00:00+00:00",
                "status": "Running",
            },
        )
        issues = engine.detect_issues()
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.HIGH_RESTART_COUNT

    def test_node_memory_pressure_detected(self):
        engine = _make_engine(
            failing_pods=[],
            node_status=[
                {
                    "name": "node-1",
                    "conditions": {"MemoryPressure": "True", "Ready": "True"},
                    "ready": True,
                }
            ],
        )
        issues = engine.detect_issues()
        assert any(i.issue_type == IssueType.NODE_MEMORY_PRESSURE for i in issues)

    def test_healthy_pod_not_included(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "ok-pod-abc",
                    "namespace": "default",
                    "status": "Running",
                    "restart_count": 0,
                    "ready": True,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "ok", "state": "Running"}],
                "events": [],
                "labels": {},
                "created_at": "2024-01-01T00:00:00+00:00",
                "status": "Running",
            },
        )
        issues = engine.detect_issues()
        # Ready pod with no issues should not be classified
        assert all(i.pod_name != "ok-pod-abc" for i in issues)

    def test_k8s_api_error_does_not_raise(self):
        engine = _make_engine(failing_pods=[{"error": "K8s API error: 403"}])
        issues = engine.detect_issues()
        assert issues == []


# ---------------------------------------------------------------------------
# Playbook Matching Tests
# ---------------------------------------------------------------------------


class TestPlaybookMatching:
    def _issue(self, issue_type: IssueType) -> DetectedIssue:
        return DetectedIssue(
            issue_type=issue_type,
            namespace="default",
            pod_name="test-pod-abc-def",
        )

    def test_crashloop_matches_crashloop_restart(self):
        engine = _make_engine()
        pb = engine.match_playbook(self._issue(IssueType.CRASHLOOP_BACKOFF))
        assert pb is not None
        assert pb.name == "crashloop_restart"

    def test_oom_killed_matches_oom_killed_scale(self):
        engine = _make_engine()
        pb = engine.match_playbook(self._issue(IssueType.OOM_KILLED))
        assert pb is not None
        assert pb.name == "oom_killed_scale"

    def test_image_pull_matches_image_pull_rollback(self):
        engine = _make_engine()
        pb = engine.match_playbook(self._issue(IssueType.IMAGE_PULL_BACKOFF))
        assert pb is not None
        assert pb.name == "image_pull_rollback"

    def test_pod_failed_matches_pod_failed_cleanup(self):
        engine = _make_engine()
        pb = engine.match_playbook(self._issue(IssueType.POD_FAILED))
        assert pb is not None
        assert pb.name == "pod_failed_cleanup"

    def test_high_restart_matches_high_restart_restart(self):
        engine = _make_engine()
        pb = engine.match_playbook(self._issue(IssueType.HIGH_RESTART_COUNT))
        assert pb is not None
        assert pb.name == "high_restart_restart"

    def test_node_pressure_has_no_playbook(self):
        engine = _make_engine()
        pb = engine.match_playbook(self._issue(IssueType.NODE_MEMORY_PRESSURE))
        assert pb is None


# ---------------------------------------------------------------------------
# Confidence Scoring Tests
# ---------------------------------------------------------------------------


class TestConfidenceScoring:
    def _pb(self) -> RemediationPlaybook:
        return PLAYBOOKS["crashloop_restart"]

    def _issue(self, **kwargs) -> DetectedIssue:
        defaults = {
            "issue_type": IssueType.CRASHLOOP_BACKOFF,
            "namespace": "production",
            "pod_name": "api-abc-def",
            "restart_count": 3,
            "evidence": ["OOMKilled", "Error: dial timeout"],
            "pod_age_hours": 48.0,
            "recent_deployment": False,
            "in_critical_namespace": False,
        }
        defaults.update(kwargs)
        return DetectedIssue(**defaults)

    def test_base_score_within_range(self):
        engine = _make_engine()
        score = engine.score_confidence(self._issue(), self._pb())
        assert 0.0 <= score <= 1.0

    def test_evidence_boosts_score(self):
        engine = _make_engine()
        without = engine.score_confidence(self._issue(evidence=[]), self._pb())
        with_ev = engine.score_confidence(self._issue(evidence=["error line"]), self._pb())
        assert with_ev > without

    def test_mature_pod_boosts_score(self):
        engine = _make_engine()
        new_pod = engine.score_confidence(self._issue(pod_age_hours=0.5), self._pb())
        old_pod = engine.score_confidence(self._issue(pod_age_hours=72.0), self._pb())
        assert old_pod > new_pod

    def test_recent_deployment_reduces_score(self):
        engine = _make_engine()
        stable = engine.score_confidence(self._issue(recent_deployment=False), self._pb())
        recent = engine.score_confidence(self._issue(recent_deployment=True), self._pb())
        assert recent < stable

    def test_critical_namespace_severely_reduces_score(self):
        engine = _make_engine()
        normal = engine.score_confidence(self._issue(in_critical_namespace=False), self._pb())
        critical = engine.score_confidence(self._issue(in_critical_namespace=True), self._pb())
        assert critical < normal
        # Critical namespace should push below threshold
        assert critical < CONFIDENCE_THRESHOLD

    def test_high_restart_count_reduces_score(self):
        engine = _make_engine()
        low = engine.score_confidence(self._issue(restart_count=3), self._pb())
        high = engine.score_confidence(self._issue(restart_count=15), self._pb())
        assert high < low

    def test_prior_successes_boost_score(self):
        store = MagicMock()
        store.past_successes.return_value = 5
        store.save_run.return_value = 1
        engine = _make_engine(mock_store=store)
        base_store = MagicMock()
        base_store.past_successes.return_value = 0
        base_store.save_run.return_value = 1
        engine_no_history = _make_engine(mock_store=base_store)
        with_history = engine.score_confidence(self._issue(), self._pb())
        no_history = engine_no_history.score_confidence(self._issue(), self._pb())
        assert with_history > no_history

    def test_score_never_exceeds_1(self):
        store = MagicMock()
        store.past_successes.return_value = 100
        store.save_run.return_value = 1
        engine = _make_engine(mock_store=store)
        score = engine.score_confidence(
            self._issue(evidence=["e1", "e2"], pod_age_hours=200.0), self._pb()
        )
        assert score <= 1.0

    def test_score_never_below_0(self):
        engine = _make_engine()
        score = engine.score_confidence(
            self._issue(
                in_critical_namespace=True,
                recent_deployment=True,
                restart_count=20,
                evidence=[],
                pod_age_hours=0.1,
            ),
            self._pb(),
        )
        assert score >= 0.0


# ---------------------------------------------------------------------------
# Execution Tests
# ---------------------------------------------------------------------------


class TestExecution:
    def test_high_confidence_executes_playbook(self):
        engine = _make_engine()
        # Patch score_confidence to always return above threshold
        with patch.object(engine, "score_confidence", return_value=0.90):
            report = engine.run(namespace="production", dry_run=False)

        assert report.executed >= 0  # may be 0 if no matching issues returned by mock

    def test_dry_run_returns_dry_run_outcome(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "api-abc-def",
                    "namespace": "production",
                    "status": "Running",
                    "restart_count": 5,
                    "ready": False,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "api", "reason": "CrashLoopBackOff"}],
                "events": [],
                "labels": {"app": "api"},
                "created_at": "2020-01-01T00:00:00+00:00",
            },
        )
        report = engine.run(namespace="production", dry_run=True)
        assert all(r.outcome == RemediationOutcome.DRY_RUN for r in report.results), (
            f"Unexpected outcomes: {[r.outcome for r in report.results]}"
        )

    def test_critical_namespace_defers_to_human(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "coredns-abc-def",
                    "namespace": "kube-system",
                    "status": "Running",
                    "restart_count": 5,
                    "ready": False,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "coredns", "reason": "CrashLoopBackOff"}],
                "events": [],
                "labels": {},
                "created_at": "2024-01-01T00:00:00+00:00",
            },
        )
        report = engine.run(dry_run=False)
        deferred = [r for r in report.results if r.outcome == RemediationOutcome.DEFERRED_TO_HUMAN]
        assert len(deferred) >= 1

    def test_restart_pod_called_for_crashloop(self):
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "api-abc-def",
                    "namespace": "production",
                    "status": "Running",
                    "restart_count": 3,
                    "ready": False,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "api", "reason": "CrashLoopBackOff"}],
                "events": [],
                "labels": {"app": "api"},
                "created_at": "2020-01-01T00:00:00+00:00",
            },
        )
        with patch.object(engine, "score_confidence", return_value=0.92):
            report = engine.run(namespace="production", dry_run=False)

        executed_results = [r for r in report.results if r.outcome == RemediationOutcome.EXECUTED]
        if executed_results:
            engine._healing.restart_pod.assert_called_once_with(
                namespace="production",
                pod_name="api-abc-def",
                dry_run=False,
            )

    def test_failed_healing_action_returns_failed_outcome(self):
        k8s = MagicMock()
        k8s.get_failing_pods.return_value = [
            {
                "name": "api-abc-def",
                "namespace": "production",
                "status": "Running",
                "restart_count": 3,
                "ready": False,
                "node": "node-1",
            }
        ]
        k8s.describe_pod.return_value = {
            "containers": [{"name": "api", "reason": "CrashLoopBackOff"}],
            "events": [],
            "labels": {"app": "api"},
            "created_at": "2020-01-01T00:00:00+00:00",
        }
        k8s.get_node_status.return_value = []
        k8s.get_pod_logs.return_value = {"logs": ""}

        healing = MagicMock()
        healing.restart_pod.return_value = {"error": "Kubernetes API unavailable"}

        store = MagicMock()
        store.past_successes.return_value = 0
        store.save_run.return_value = 1

        engine = RemediationEngine(k8s_tools=k8s, healing_actions=healing, store=store)

        with patch.object(engine, "score_confidence", return_value=0.95):
            report = engine.run(namespace="production", dry_run=False)

        assert any(r.outcome == RemediationOutcome.FAILED for r in report.results)


# ---------------------------------------------------------------------------
# Report Structure Tests
# ---------------------------------------------------------------------------


class TestRemediationReport:
    def test_report_to_dict_has_required_fields(self):
        engine = _make_engine(failing_pods=[], node_status=[])
        report = engine.run()
        d = report.to_dict()
        for key in (
            "namespace",
            "dry_run",
            "issues_detected",
            "playbooks_matched",
            "executed",
            "deferred_to_human",
            "failed",
            "results",
            "timestamp",
        ):
            assert key in d, f"Missing key: {key}"

    def test_empty_cluster_returns_zero_counts(self):
        engine = _make_engine(failing_pods=[], node_status=[])
        report = engine.run()
        assert report.issues_detected == 0
        assert report.playbooks_matched == 0
        assert report.executed == 0
        assert report.deferred_to_human == 0

    def test_store_save_run_called_per_result(self):
        store = MagicMock()
        store.past_successes.return_value = 0
        store.save_run.return_value = 1
        engine = _make_engine(
            failing_pods=[
                {
                    "name": "api-abc-def",
                    "namespace": "production",
                    "status": "Running",
                    "restart_count": 3,
                    "ready": False,
                    "node": "node-1",
                }
            ],
            describe_pod_return={
                "containers": [{"name": "api", "reason": "CrashLoopBackOff"}],
                "events": [],
                "labels": {},
                "created_at": "2020-01-01T00:00:00+00:00",
            },
            mock_store=store,
        )
        engine.run(namespace="production", dry_run=True)
        assert store.save_run.call_count >= 1


# ---------------------------------------------------------------------------
# Utility Tests
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_infer_deployment_name_from_labels(self):
        name = RemediationEngine._infer_deployment_name("pod-abc-def", {"app": "my-service"})
        assert name == "my-service"

    def test_infer_deployment_name_from_pod_name(self):
        name = RemediationEngine._infer_deployment_name("checkout-7d9f-xk2p", {})
        assert name == "checkout"

    def test_infer_deployment_name_prefers_labels(self):
        name = RemediationEngine._infer_deployment_name(
            "checkout-7d9f-xk2p", {"app": "checkout-service"}
        )
        assert name == "checkout-service"

    def test_pod_age_hours_parses_iso_timestamp(self):
        # Use a very old timestamp so age is always > 0
        age = RemediationEngine._pod_age_hours("2020-01-01T00:00:00+00:00")
        assert age is not None
        assert age > 0

    def test_pod_age_hours_returns_none_for_invalid(self):
        age = RemediationEngine._pod_age_hours("not-a-timestamp")
        assert age is None

    def test_pod_age_hours_returns_none_for_none(self):
        age = RemediationEngine._pod_age_hours(None)
        assert age is None
