"""Plan non-trivial work before it reaches a local agent or delegated CLI."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from approval_manager import ApprovalManager
from job_manager import JobManager
from policy_engine import PolicyDecision, PolicyEngine


COMPLEX_MARKERS = (
    "workflow",
    "automatis",
    "projekt",
    "mehrere",
    "schritt",
    "plan",
    "mail",
    "excel",
    "pdf",
    "test",
    "agent",
    "codex",
    "open code",
    "opencode",
)
RISK_MARKERS = {
    "send_mail": ("mail senden", "verschicke", "sende die mail"),
    "delete": ("lösche", "loesche", "entferne dauerhaft"),
    "publish": ("veröffentliche", "veroeffentliche", "publiziere"),
    "external_upload": ("hochladen", "upload", "teile extern"),
    "install_package": ("installiere paket", "pip install", "npm install"),
}


@dataclass
class TaskDecision:
    route: str
    job: Optional[dict]
    approval: Optional[dict]
    requires_plan: bool
    blocked: bool
    message: str = ""

    def summary(self) -> dict:
        return {
            "route": self.route,
            "job_id": (self.job or {}).get("job_id", ""),
            "approval_id": (self.approval or {}).get("approval_id", ""),
            "requires_plan": self.requires_plan,
            "blocked": self.blocked,
            "message": self.message,
        }


class TaskOrchestrator:
    """Create transparent plans, jobs and approvals without replacing legacy routing."""

    def __init__(self, home: Optional[str | Path] = None):
        self.home = Path(home or Path(__file__).resolve().parents[1]).resolve()
        self.jobs = JobManager(self.home)
        self.approvals = ApprovalManager(self.home)
        self.policy = PolicyEngine()

    def prepare(
        self,
        query: str,
        source: str = "desktop",
        route: str = "",
    ) -> TaskDecision:
        text = str(query or "").strip()
        selected_route = route or self._route_for(text)
        requires_plan = self._requires_plan(text, selected_route)
        risk_action = self._risk_action(text)

        if risk_action:
            policy = self.policy.decide(risk_action)
            if not policy.allowed:
                return TaskDecision(
                    selected_route,
                    None,
                    None,
                    requires_plan,
                    True,
                    policy.reason,
                )
            job = self.jobs.create_job(
                self._title(text),
                source=source,
                route=selected_route,
                risk_level="high",
                plan=self._plan_steps(selected_route, approval=True),
                metadata={"query": text, "risk_action": risk_action},
            )
            approval = self.approvals.request(
                job["job_id"],
                risk_action,
                f"Freigabe fuer: {self._title(text)}",
                risk_level="high",
                details={"query": text, "route": selected_route},
            )
            self.jobs.set_status(
                job["job_id"],
                "WAITING_FOR_APPROVAL",
                "Auftrag wartet auf explizite Freigabe.",
                {"approval_id": approval["approval_id"]},
            )
            return TaskDecision(
                selected_route,
                self.jobs.get(job["job_id"]),
                approval,
                True,
                True,
                policy.reason,
            )

        if not requires_plan:
            return TaskDecision(selected_route, None, None, False, False)

        job = self.jobs.create_job(
            self._title(text),
            source=source,
            route=selected_route,
            risk_level="medium" if selected_route in {"codex", "opencode"} else "low",
            plan=self._plan_steps(selected_route),
            metadata={"query": text},
        )
        self.jobs.start(job["job_id"], "Plan angelegt; Ausfuehrung wird vorbereitet.")
        first_step = self.jobs.get(job["job_id"])["steps"][0]
        self.jobs.update_step(
            job["job_id"],
            first_step["step_id"],
            "SUCCEEDED",
            {"quality_gate": "Projekt, Auftrag und Grenzen erfasst."},
        )
        return TaskDecision(selected_route, self.jobs.get(job["job_id"]), None, True, False)

    def finish(
        self,
        decision: Optional[TaskDecision],
        result_summary: str,
        succeeded: bool = True,
        details: Optional[dict] = None,
    ) -> None:
        if decision is None or not decision.job:
            return
        job = self.jobs.get(decision.job["job_id"])
        if job["status"] in {"WAITING_FOR_APPROVAL", "CANCELLED"}:
            return
        steps = job["steps"]
        if len(steps) > 1:
            self.jobs.update_step(
                job["job_id"],
                steps[1]["step_id"],
                "SUCCEEDED" if succeeded else "FAILED",
                {"result_summary": result_summary[:2000], **(details or {})},
            )
        if len(steps) > 2:
            self.jobs.update_step(
                job["job_id"],
                steps[2]["step_id"],
                "SUCCEEDED" if succeeded else "FAILED",
                {
                    "quality_gate": (
                        "Delegierter Lauf hat einen Abschlussbericht geliefert."
                        if succeeded
                        else "Delegierter Lauf ist fehlgeschlagen."
                    )
                },
            )
        if len(steps) > 3:
            self.jobs.update_step(
                job["job_id"],
                steps[3]["step_id"],
                "SUCCEEDED" if succeeded else "FAILED",
                {"report": "Trinity hat den Abschluss gespeichert."},
            )
        if succeeded:
            self.jobs.complete(
                job["job_id"],
                "Auftrag mit Plan und Abschlussbericht beendet.",
                {"result_summary": result_summary[:2000], **(details or {})},
            )
        else:
            self.jobs.fail(
                job["job_id"],
                "Auftrag fehlgeschlagen; Abschlussbericht gespeichert.",
                {"result_summary": result_summary[:2000], **(details or {})},
            )

    def preview(self, query: str, source: str = "desktop") -> dict:
        decision = self.prepare(query, source=source)
        return decision.summary()

    @staticmethod
    def _route_for(text: str) -> str:
        normalized = text.casefold()
        if re.search(r"\b(open[- ]?code|opencode)\b", normalized):
            return "opencode"
        if re.search(r"\b(codex|kodeks)\b", normalized):
            return "codex"
        if "agent forge" in normalized or "neuen agent" in normalized:
            return "agent_forge"
        return "local"

    @staticmethod
    def _requires_plan(text: str, route: str) -> bool:
        normalized = text.casefold()
        if route in {"codex", "opencode", "agent_forge"}:
            return True
        return len(normalized.split()) >= 18 and any(
            marker in normalized for marker in COMPLEX_MARKERS
        )

    @staticmethod
    def _risk_action(text: str) -> str:
        normalized = text.casefold()
        for action, markers in RISK_MARKERS.items():
            if any(marker in normalized for marker in markers):
                return action
        return ""

    @staticmethod
    def _title(text: str) -> str:
        compact = " ".join(text.split())
        return compact[:120] or "Trinity-Auftrag"

    @staticmethod
    def _plan_steps(route: str, approval: bool = False) -> list[dict]:
        steps = [
            {
                "title": "Auftrag, Projekt und Sicherheitsgrenzen pruefen",
                "quality_gate": True,
            }
        ]
        if approval:
            steps.append(
                {
                    "title": "Explizite Freigabe einholen",
                    "quality_gate": True,
                }
            )
        steps.extend(
            [
                {
                    "title": (
                        "Delegierten Agenten ausfuehren"
                        if route in {"codex", "opencode"}
                        else "Lokalen Workflow ausfuehren"
                    ),
                    "quality_gate": False,
                },
                {
                    "title": "Ergebnis und Tests gegen den Auftrag pruefen",
                    "quality_gate": True,
                },
                {
                    "title": "Abschlussbericht, Artefakte und Audit-Eintrag speichern",
                    "quality_gate": True,
                },
            ]
        )
        return steps
