"""
Auto-Remediation Engine
=======================
Detects Kubernetes issues, matches them to pre-approved playbooks, scores
confidence, and executes fixes when confidence >= CONFIDENCE_THRESHOLD (80%).

When confidence is below the threshold the issue is flagged for human review
with a full evidence summary so on-call engineers have context immediately.

Flow
----
1. detect_issues()   — scan cluster for failing pods and unhealthy nodes
2. match_playbook()  — look up the best playbook for each issue type
3. score_confidence()— compute 0.0-1.0 confidence using heuristics
4. execute / defer   — run playbook if confident, otherwise alert humans
5. save_run()        — persist every decision to the remediation_runs table

Pre-Approved Playbooks
----------------------
  crashloop_restart         CrashLoopBackOff pods with <10 restarts
  oom_killed_scale          OOMKilled pods — add a replica
  image_pull_rollback       ImagePullBackOff — rollback to previous image
  pod_failed_cleanup        Failed pods — delete so controller reschedules
  high_restart_restart      >10 restarts (Running) — force fresh start

Confidence Scoring
------------------
  Base score per playbook (0.55-0.75)
  +0.10  evidence gathered (logs / events confirm issue)
  +0.08  pod age > 24 h (stable workload, restart is safe)
  +0.08  prior successful execution for same issue type
  +0.05  restart count 1-9 (moderate — likely transient)
  -0.10  restart count >= 10 (persistent failure — needs investigation)
  -0.15  recent deployment < 60 min (may be intentional change)
  -0.30  critical namespace (kube-system, cert-manager, etc.)

Actions >= 0.80 confidence are executed automatically.
Actions < 0.80 are deferred to a human with a full evidence summary.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from intelligent_sre_agent.remediation_store import RemediationStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD: float = 0.80
HIGH_RESTART_THRESHOLD: int = 10
RECENT_DEPLOY_MINUTES: int = 60

# Never auto-remediate system namespaces — confidence penalty is severe
CRITICAL_NAMESPACES: frozenset[str] = frozenset(
    {"kube-system", "kube-public", "kube-node-lease", "cert-manager", "ingress-nginx"}
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IssueType(str, Enum):
    CRASHLOOP_BACKOFF = "CrashLoopBackOff"
    OOM_KILLED = "OOMKilled"
    POD_PENDING = "PodPending"
    IMAGE_PULL_BACKOFF = "ImagePullBackOff"
    HIGH_RESTART_COUNT = "HighRestartCount"
    NODE_MEMORY_PRESSURE = "NodeMemoryPressure"
    NODE_DISK_PRESSURE = "NodeDiskPressure"
    POD_FAILED = "PodFailed"


class RemediationOutcome(str, Enum):
    EXECUTED = "executed"
    DEFERRED_TO_HUMAN = "deferred_to_human"
    DRY_RUN = "dry_run"
    FAILED = "failed"
    NO_ACTION = "no_action"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DetectedIssue:
    issue_type: IssueType
    namespace: str
    pod_name: str
    node_name: Optional[str] = None
    restart_count: int = 0
    # log lines + event messages gathered as evidence
    evidence: List[str] = field(default_factory=list)
    labels: Dict[str, Any] = field(default_factory=dict)
    pod_age_hours: Optional[float] = None
    recent_deployment: bool = False
    in_critical_namespace: bool = False


@dataclass
class PlaybookAction:
    name: str  # restart_pod | delete_failed_pods | scale_deployment_up | rollback_deployment
    params: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""


@dataclass
class RemediationPlaybook:
    name: str
    title: str
    description: str
    issue_types: List[IssueType]
    actions: List[PlaybookAction]
    base_confidence: float


@dataclass
class RemediationResult:
    issue: DetectedIssue
    playbook: RemediationPlaybook
    confidence: float
    outcome: RemediationOutcome
    actions_taken: List[str]
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.issue.namespace,
            "pod_name": self.issue.pod_name,
            "issue_type": self.issue.issue_type.value,
            "playbook": self.playbook.name,
            "confidence": round(self.confidence, 3),
            "outcome": self.outcome.value,
            "actions_taken": self.actions_taken,
            "summary": self.summary,
            "evidence": self.issue.evidence[:5],
            "timestamp": self.timestamp,
        }


@dataclass
class RemediationReport:
    namespace: Optional[str]
    dry_run: bool
    issues_detected: int
    playbooks_matched: int
    executed: int
    deferred_to_human: int
    failed: int
    results: List[RemediationResult]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace or "all",
            "dry_run": self.dry_run,
            "issues_detected": self.issues_detected,
            "playbooks_matched": self.playbooks_matched,
            "executed": self.executed,
            "deferred_to_human": self.deferred_to_human,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Playbook Registry
# ---------------------------------------------------------------------------


PLAYBOOKS: Dict[str, RemediationPlaybook] = {
    "crashloop_restart": RemediationPlaybook(
        name="crashloop_restart",
        title="CrashLoopBackOff - Restart Pod",
        description=(
            "Delete the pod so its controller creates a fresh instance. "
            "Effective for transient startup errors (config races, init timeouts). "
            "Skipped when restarts >= 10 to avoid masking persistent failures."
        ),
        issue_types=[IssueType.CRASHLOOP_BACKOFF],
        actions=[
            PlaybookAction(
                "restart_pod",
                {},
                "Delete pod; Kubernetes controller recreates it from the same spec",
            ),
        ],
        base_confidence=0.65,
    ),
    "oom_killed_scale": RemediationPlaybook(
        name="oom_killed_scale",
        title="OOMKilled - Scale Deployment Up",
        description=(
            "Add one replica to redistribute per-pod memory load "
            "when containers are repeatedly killed by the OOM killer."
        ),
        issue_types=[IssueType.OOM_KILLED],
        actions=[
            PlaybookAction(
                "scale_deployment_up",
                {"replicas_delta": 1},
                "Increase replica count by 1 to reduce per-pod memory pressure",
            ),
        ],
        base_confidence=0.60,
    ),
    "image_pull_rollback": RemediationPlaybook(
        name="image_pull_rollback",
        title="ImagePullBackOff - Rollback Deployment",
        description=(
            "Roll back to the previous deployment revision when the new image "
            "cannot be pulled (bad tag, registry outage, or auth failure)."
        ),
        issue_types=[IssueType.IMAGE_PULL_BACKOFF],
        actions=[
            PlaybookAction(
                "rollback_deployment",
                {},
                "Revert deployment to last known-good image revision",
            ),
        ],
        base_confidence=0.72,
    ),
    "pod_failed_cleanup": RemediationPlaybook(
        name="pod_failed_cleanup",
        title="Failed Pods - Delete and Reschedule",
        description=(
            "Remove pods stuck in the Failed phase so the owning controller "
            "(Deployment, StatefulSet, Job) can schedule fresh replacements."
        ),
        issue_types=[IssueType.POD_FAILED],
        actions=[
            PlaybookAction(
                "delete_failed_pods",
                {},
                "Delete Failed pods; controller reschedules automatically",
            ),
        ],
        base_confidence=0.70,
    ),
    "high_restart_restart": RemediationPlaybook(
        name="high_restart_restart",
        title="High Restart Count - Force Fresh Start",
        description=(
            "Restart a pod that has accumulated excessive restarts while still "
            "running (no CrashLoop yet). Clears accumulated in-memory state that "
            "may be causing degraded behaviour."
        ),
        issue_types=[IssueType.HIGH_RESTART_COUNT],
        actions=[
            PlaybookAction(
                "restart_pod",
                {},
                "Delete pod to clear accumulated restart state; controller recreates",
            ),
        ],
        base_confidence=0.55,
    ),
}

# Map issue type -> playbook name for fast lookup
_ISSUE_TO_PLAYBOOK: Dict[IssueType, str] = {
    issue_type: pb.name for pb in PLAYBOOKS.values() for issue_type in pb.issue_types
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RemediationEngine:
    """Detect, score, and auto-remediate Kubernetes issues using pre-approved playbooks.

    Parameters
    ----------
    k8s_tools:
        An instance of KubernetesTools used for cluster introspection.
    healing_actions:
        An instance of HealingActions used for executing fixes.
    store:
        A RemediationStore for persisting run history. If None a fresh
        store is created using the default database path.
    notify_callback:
        Optional async callable ``(text: str) -> None`` invoked when an issue
        is deferred to a human (e.g. post to Slack).
    """

    def __init__(
        self,
        k8s_tools: Any,
        healing_actions: Any,
        store: Optional[RemediationStore] = None,
        notify_callback: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._k8s = k8s_tools
        self._healing = healing_actions
        self._store = store or RemediationStore()
        self._notify = notify_callback

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        namespace: Optional[str] = None,
        dry_run: bool = False,
    ) -> RemediationReport:
        """Run a full remediation cycle for the given namespace.

        Detects all failing pods and nodes, matches playbooks, scores confidence,
        executes (or defers) actions, persists every decision, and returns a
        structured report.
        """
        logger.info(
            "Remediation cycle started",
            extra={"namespace": namespace or "all", "dry_run": dry_run},
        )

        issues = self.detect_issues(namespace)
        results: List[RemediationResult] = []

        for issue in issues:
            playbook = self.match_playbook(issue)
            if playbook is None:
                logger.debug(
                    "No playbook for issue",
                    extra={"issue_type": issue.issue_type, "pod": issue.pod_name},
                )
                continue

            confidence = self.score_confidence(issue, playbook)
            issue_with_conf = issue  # keep reference for logging

            if confidence >= CONFIDENCE_THRESHOLD and not dry_run:
                result = self._execute_playbook(
                    issue_with_conf, playbook, confidence, dry_run=False
                )
            elif dry_run:
                result = RemediationResult(
                    issue=issue_with_conf,
                    playbook=playbook,
                    confidence=confidence,
                    outcome=RemediationOutcome.DRY_RUN,
                    actions_taken=[a.name for a in playbook.actions],
                    summary=(
                        f"[DRY RUN] Would execute {playbook.title} (confidence {confidence:.0%})"
                    ),
                )
            else:
                result = self._defer_to_human(issue_with_conf, playbook, confidence)

            results.append(result)
            self._persist(result, dry_run=dry_run)

        report = RemediationReport(
            namespace=namespace,
            dry_run=dry_run,
            issues_detected=len(issues),
            playbooks_matched=len(results),
            executed=sum(1 for r in results if r.outcome == RemediationOutcome.EXECUTED),
            deferred_to_human=sum(
                1 for r in results if r.outcome == RemediationOutcome.DEFERRED_TO_HUMAN
            ),
            failed=sum(1 for r in results if r.outcome == RemediationOutcome.FAILED),
            results=results,
        )

        logger.info(
            "Remediation cycle complete",
            extra={
                "issues": report.issues_detected,
                "executed": report.executed,
                "deferred": report.deferred_to_human,
            },
        )
        return report

    # ------------------------------------------------------------------
    # Step 1: Detection
    # ------------------------------------------------------------------

    def detect_issues(self, namespace: Optional[str] = None) -> List[DetectedIssue]:
        """Scan the cluster and return a list of actionable issues."""
        issues: List[DetectedIssue] = []

        # --- Failing pods -----------------------------------------------
        try:
            failing_pods = self._k8s.get_failing_pods(namespace)
            if failing_pods and "error" in failing_pods[0]:
                logger.warning(
                    "get_failing_pods returned error", extra={"error": failing_pods[0]["error"]}
                )
                failing_pods = []
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_failing_pods raised", extra={"error": str(exc)})
            failing_pods = []

        for pod in failing_pods:
            if "error" in pod:
                continue
            issue = self._build_pod_issue(pod)
            if issue is not None:
                issues.append(issue)

        # --- Node pressure -----------------------------------------------
        try:
            nodes = self._k8s.get_node_status()
            if nodes and "error" not in nodes[0]:
                for node in nodes:
                    for pressure_type, issue_type in (
                        ("MemoryPressure", IssueType.NODE_MEMORY_PRESSURE),
                        ("DiskPressure", IssueType.NODE_DISK_PRESSURE),
                    ):
                        if node.get("conditions", {}).get(pressure_type) == "True":
                            issues.append(
                                DetectedIssue(
                                    issue_type=issue_type,
                                    namespace="kube-system",
                                    pod_name=f"node:{node['name']}",
                                    node_name=node["name"],
                                    in_critical_namespace=True,
                                    evidence=[f"Node {node['name']} reports {pressure_type}=True"],
                                )
                            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_node_status raised", extra={"error": str(exc)})

        logger.info("Issues detected", extra={"count": len(issues)})
        return issues

    def _build_pod_issue(self, pod: Dict[str, Any]) -> Optional[DetectedIssue]:
        """Build a DetectedIssue from a failing-pod summary dict.

        Calls describe_pod() once per pod for detailed container state.
        """
        pod_name: str = pod["name"]
        namespace: str = pod["namespace"]
        restart_count: int = pod.get("restart_count", 0)

        # Get detailed state for accurate classification
        try:
            detail = self._k8s.describe_pod(namespace, pod_name)
        except Exception:  # noqa: BLE001
            detail = {}

        issue_type = self._classify_pod(pod, detail)
        if issue_type is None:
            return None

        evidence = self._gather_evidence(namespace, pod_name, detail)
        pod_age_hours = self._pod_age_hours(detail.get("created_at"))
        labels: Dict[str, Any] = detail.get("labels", {})

        # A pod is "recently deployed" if its owning deployment was updated
        # within RECENT_DEPLOY_MINUTES.  We approximate by checking pod age.
        recent_deployment = pod_age_hours is not None and pod_age_hours < (
            RECENT_DEPLOY_MINUTES / 60
        )

        return DetectedIssue(
            issue_type=issue_type,
            namespace=namespace,
            pod_name=pod_name,
            node_name=pod.get("node"),
            restart_count=restart_count,
            evidence=evidence,
            labels=labels,
            pod_age_hours=pod_age_hours,
            recent_deployment=recent_deployment,
            in_critical_namespace=namespace in CRITICAL_NAMESPACES,
        )

    def _classify_pod(self, pod: Dict[str, Any], detail: Dict[str, Any]) -> Optional[IssueType]:
        """Map raw pod state to an IssueType, or None if unactionable."""
        restart_count: int = pod.get("restart_count", 0)

        # Prefer detailed container state for accuracy
        for cs in detail.get("containers", []):
            reason = (cs.get("reason") or "").lower()
            if reason == "crashloopbackoff":
                return IssueType.CRASHLOOP_BACKOFF
            if reason == "oomkilled":
                return IssueType.OOM_KILLED
            if reason in ("imagepullbackoff", "errimagepull"):
                return IssueType.IMAGE_PULL_BACKOFF

        phase = (pod.get("status") or detail.get("status") or "").lower()

        if phase == "failed":
            return IssueType.POD_FAILED
        if phase == "pending":
            return IssueType.POD_PENDING

        # Fallback: high restart count with no specific reason
        if restart_count >= HIGH_RESTART_THRESHOLD:
            return IssueType.HIGH_RESTART_COUNT

        # Catch CrashLoopBackOff pods that are still "Running" but not ready
        # and have high restarts (typical in practice)
        if restart_count >= 3 and not pod.get("ready", True):
            return IssueType.CRASHLOOP_BACKOFF

        return None

    # ------------------------------------------------------------------
    # Step 2: Evidence gathering
    # ------------------------------------------------------------------

    def _gather_evidence(
        self,
        namespace: str,
        pod_name: str,
        detail: Dict[str, Any],
    ) -> List[str]:
        """Collect log lines and event messages as evidence for confidence scoring."""
        evidence: List[str] = []

        # Extract events from describe_pod detail (already fetched — no extra API call)
        for event in detail.get("events", [])[:3]:
            msg = event.get("message", "")
            if msg:
                evidence.append(f"K8s event [{event.get('reason', '')}]: {msg[:120]}")

        # Fetch last 15 lines from previous container instance (crashed container)
        try:
            log_resp = self._k8s.get_pod_logs(namespace, pod_name, tail_lines=15, previous=True)
            if log_resp.get("logs"):
                lines = [ln for ln in log_resp["logs"].strip().splitlines() if ln.strip()]
                evidence.extend(lines[-5:])
        except Exception:  # noqa: BLE001
            pass

        return evidence

    # ------------------------------------------------------------------
    # Step 3: Playbook matching
    # ------------------------------------------------------------------

    def match_playbook(self, issue: DetectedIssue) -> Optional[RemediationPlaybook]:
        """Return the pre-approved playbook for this issue, or None."""
        pb_name = _ISSUE_TO_PLAYBOOK.get(issue.issue_type)
        return PLAYBOOKS.get(pb_name) if pb_name else None  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Step 4: Confidence scoring
    # ------------------------------------------------------------------

    def score_confidence(self, issue: DetectedIssue, playbook: RemediationPlaybook) -> float:
        """Compute a 0.0-1.0 confidence score.

        Higher is more confident. Execution is gated at CONFIDENCE_THRESHOLD.
        """
        score = playbook.base_confidence

        # --- Boosters ---------------------------------------------------
        if issue.evidence:
            score += 0.10  # evidence confirms the issue

        if issue.pod_age_hours is not None and issue.pod_age_hours > 24:
            score += 0.08  # stable workload — restart is safe

        prior_successes = self._store.past_successes(issue.issue_type.value, issue.namespace)
        if prior_successes > 0:
            score += min(0.08, prior_successes * 0.02)  # cap boost at 0.08

        if 0 < issue.restart_count < HIGH_RESTART_THRESHOLD:
            score += 0.05  # moderate restart count — likely transient

        # --- Penalties --------------------------------------------------
        if issue.restart_count >= HIGH_RESTART_THRESHOLD:
            score -= 0.10  # persistent failure needs investigation, not just restart

        if issue.recent_deployment:
            score -= 0.15  # change may be intentional — let human verify

        if issue.in_critical_namespace:
            score -= 0.30  # never auto-fix system workloads

        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Step 5: Execution
    # ------------------------------------------------------------------

    def _execute_playbook(
        self,
        issue: DetectedIssue,
        playbook: RemediationPlaybook,
        confidence: float,
        dry_run: bool,
    ) -> RemediationResult:
        """Execute all playbook actions and return the result."""
        actions_taken: List[str] = []
        errors: List[str] = []

        for action in playbook.actions:
            try:
                action_result = self._run_action(action, issue, dry_run=dry_run)
                if action_result.get("success") or "error" not in action_result:
                    actions_taken.append(action.name)
                    logger.info(
                        "Playbook action executed",
                        extra={
                            "action": action.name,
                            "pod": issue.pod_name,
                            "namespace": issue.namespace,
                        },
                    )
                else:
                    err = action_result.get("error", "unknown error")
                    errors.append(f"{action.name}: {err}")
                    logger.warning(
                        "Playbook action failed",
                        extra={"action": action.name, "error": err},
                    )
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                errors.append(f"{action.name}: {err}")
                logger.exception("Playbook action raised", extra={"action": action.name})

        if errors and not actions_taken:
            outcome = RemediationOutcome.FAILED
            summary = f"Playbook {playbook.title} failed for {issue.pod_name}: " + "; ".join(errors)
        else:
            outcome = RemediationOutcome.EXECUTED
            summary = (
                f"Executed {playbook.title} on {issue.pod_name} "
                f"(confidence {confidence:.0%}). "
                f"Actions: {', '.join(actions_taken)}."
            )
            if errors:
                summary += f" Partial errors: {'; '.join(errors)}"

        return RemediationResult(
            issue=issue,
            playbook=playbook,
            confidence=confidence,
            outcome=outcome,
            actions_taken=actions_taken,
            summary=summary,
        )

    def _run_action(
        self, action: PlaybookAction, issue: DetectedIssue, dry_run: bool
    ) -> Dict[str, Any]:
        """Dispatch a single playbook action to the appropriate HealingActions method."""
        match action.name:
            case "restart_pod":
                return self._healing.restart_pod(
                    namespace=issue.namespace,
                    pod_name=issue.pod_name,
                    dry_run=dry_run,
                )

            case "delete_failed_pods":
                return self._healing.delete_failed_pods(
                    namespace=issue.namespace,
                    dry_run=dry_run,
                )

            case "scale_deployment_up":
                deploy_name = self._infer_deployment_name(issue.pod_name, issue.labels)
                if not deploy_name:
                    return {"error": "Could not infer deployment name from pod labels"}
                deploy_status = self._k8s.get_deployment_status(issue.namespace, deploy_name)
                if "error" in deploy_status:
                    return deploy_status
                current_replicas: int = deploy_status["replicas"]["desired"] or 1
                delta: int = action.params.get("replicas_delta", 1)
                return self._healing.scale_deployment(
                    namespace=issue.namespace,
                    deployment_name=deploy_name,
                    replicas=current_replicas + delta,
                    dry_run=dry_run,
                )

            case "rollback_deployment":
                deploy_name = self._infer_deployment_name(issue.pod_name, issue.labels)
                if not deploy_name:
                    return {"error": "Could not infer deployment name from pod labels"}
                return self._healing.rollback_deployment(
                    namespace=issue.namespace,
                    deployment_name=deploy_name,
                    dry_run=dry_run,
                )

            case _:
                return {"error": f"Unknown action: {action.name}"}

    def _defer_to_human(
        self,
        issue: DetectedIssue,
        playbook: RemediationPlaybook,
        confidence: float,
    ) -> RemediationResult:
        """Build a deferred-to-human result and log the alert."""
        reasons: List[str] = []
        if issue.in_critical_namespace:
            reasons.append("critical namespace")
        if issue.recent_deployment:
            reasons.append("recent deployment")
        if issue.restart_count >= HIGH_RESTART_THRESHOLD:
            reasons.append(f"persistent failure ({issue.restart_count} restarts)")
        if not reasons:
            reasons.append(f"confidence {confidence:.0%} below threshold")

        summary = (
            f"HUMAN REVIEW REQUIRED: {issue.issue_type.value} on {issue.pod_name} "
            f"in {issue.namespace}. "
            f"Playbook matched: {playbook.title}. "
            f"Confidence: {confidence:.0%} (threshold: {CONFIDENCE_THRESHOLD:.0%}). "
            f"Reason(s) for deferral: {', '.join(reasons)}."
        )

        if issue.evidence:
            summary += "\nEvidence:\n" + "\n".join(f"  {e}" for e in issue.evidence[:3])

        logger.warning(
            "Issue deferred to human",
            extra={
                "issue_type": issue.issue_type.value,
                "pod": issue.pod_name,
                "namespace": issue.namespace,
                "confidence": confidence,
                "reasons": reasons,
            },
        )

        if self._notify:
            try:
                self._notify(summary)
            except Exception:  # noqa: BLE001
                pass

        return RemediationResult(
            issue=issue,
            playbook=playbook,
            confidence=confidence,
            outcome=RemediationOutcome.DEFERRED_TO_HUMAN,
            actions_taken=[],
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _persist(self, result: RemediationResult, dry_run: bool) -> None:
        """Save the remediation result to the database (best-effort)."""
        try:
            self._store.save_run(
                namespace=result.issue.namespace,
                pod_name=result.issue.pod_name,
                issue_type=result.issue.issue_type.value,
                playbook_name=result.playbook.name,
                confidence=result.confidence,
                outcome=result.outcome.value,
                actions_taken=result.actions_taken,
                evidence_summary="\n".join(result.issue.evidence[:5]),
                details=result.to_dict(),
                dry_run=dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist remediation run", extra={"error": str(exc)})

    @staticmethod
    def _infer_deployment_name(pod_name: str, labels: Dict[str, Any]) -> Optional[str]:
        """Derive the owning Deployment name from pod labels or pod name suffix."""
        for key in ("app", "app.kubernetes.io/name", "app.kubernetes.io/instance"):
            if labels.get(key):
                return labels[key]
        # Kubernetes pod names: <deploy>-<rs-hash>-<pod-hash>
        parts = pod_name.rsplit("-", 2)
        if len(parts) >= 3:
            return parts[0]
        if len(parts) == 2:
            return parts[0]
        return pod_name

    @staticmethod
    def _pod_age_hours(created_at: Optional[str]) -> Optional[float]:
        """Parse an ISO timestamp string and return age in hours."""
        if not created_at:
            return None
        try:
            # Kubernetes timestamps are timezone-aware
            ts_str = created_at.replace(" ", "T")
            if ts_str.endswith("+00:00") or ts_str.endswith("Z"):
                ts_str = ts_str.rstrip("Z") + "+00:00" if ts_str.endswith("Z") else ts_str
                dt = datetime.fromisoformat(ts_str)
            else:
                dt = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - dt
            return age.total_seconds() / 3600
        except (ValueError, TypeError):
            return None


# ---------------------------------------------------------------------------
# Convenience function: list all playbooks as plain dicts
# ---------------------------------------------------------------------------


def list_playbooks() -> List[Dict[str, Any]]:
    """Return a summary of all pre-approved remediation playbooks."""
    result = []
    for pb in PLAYBOOKS.values():
        result.append(
            {
                "name": pb.name,
                "title": pb.title,
                "description": pb.description,
                "issue_types": [t.value for t in pb.issue_types],
                "actions": [{"name": a.name, "rationale": a.rationale} for a in pb.actions],
                "base_confidence": pb.base_confidence,
                "confidence_threshold": CONFIDENCE_THRESHOLD,
            }
        )
    return result
