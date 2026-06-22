"""Three-tier skill registry with backward compatibility for existing agents."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


TIERS = ("shared", "personal", "staging")
ACTIVE_TIERS = {"shared", "personal"}
VALID_STATUSES = {"active", "staging", "disabled", "archived"}
REQUIRED_MANIFEST_FIELDS = {
    "id",
    "name",
    "version",
    "tier",
    "description",
    "triggers",
    "allowed_tools",
    "allowed_paths",
    "requires_approval",
    "tests",
    "status",
}
SKILL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


@dataclass
class SkillManifest:
    """Validated metadata for a managed skill."""

    skill_id: str
    name: str
    version: str
    tier: str
    description: str
    triggers: list[str]
    allowed_tools: list[str]
    allowed_paths: list[str]
    requires_approval: list[str]
    tests: list[str]
    status: str
    script: str = "script.py"
    risk_level: str = "low"
    source: str = "managed"
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path, expected_tier: str) -> "SkillManifest":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Manifest muss ein JSON-Objekt sein.")
        missing = sorted(REQUIRED_MANIFEST_FIELDS - set(data))
        if missing:
            raise ValueError(f"Pflichtfelder fehlen: {', '.join(missing)}")

        manifest = cls(
            skill_id=str(data["id"]).strip(),
            name=str(data["name"]).strip(),
            version=str(data["version"]).strip(),
            tier=str(data["tier"]).strip().lower(),
            description=str(data["description"]).strip(),
            triggers=_string_list(data["triggers"], "triggers"),
            allowed_tools=_string_list(data["allowed_tools"], "allowed_tools"),
            allowed_paths=_string_list(data["allowed_paths"], "allowed_paths"),
            requires_approval=_string_list(
                data["requires_approval"], "requires_approval"
            ),
            tests=_string_list(data["tests"], "tests"),
            status=str(data["status"]).strip().lower(),
            script=str(data.get("script", "script.py")).strip() or "script.py",
            risk_level=str(data.get("risk_level", "low")).strip().lower() or "low",
            raw=data,
        )
        manifest.validate(expected_tier)
        return manifest

    def validate(self, expected_tier: str) -> None:
        if not SKILL_ID_PATTERN.fullmatch(self.skill_id):
            raise ValueError("id muss aus Kleinbuchstaben, Ziffern, _ oder - bestehen.")
        if self.tier not in TIERS:
            raise ValueError(f"Unbekannter Skill-Tier: {self.tier}")
        if self.tier != expected_tier:
            raise ValueError(
                f"Manifest-Tier {self.tier} passt nicht zum Ordner {expected_tier}."
            )
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Unbekannter Skill-Status: {self.status}")
        if not self.name or not self.description:
            raise ValueError("name und description duerfen nicht leer sein.")
        if not self.triggers:
            raise ValueError("triggers darf nicht leer sein.")
        if self.tier == "staging" and not self.tests:
            raise ValueError("Staging-Skills brauchen mindestens einen Test.")


@dataclass
class SkillRecord:
    manifest: SkillManifest
    directory: Path
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    legacy: bool = False

    @property
    def is_active(self) -> bool:
        return (
            self.valid
            and not self.legacy
            and self.manifest.tier in ACTIVE_TIERS
            and self.manifest.status == "active"
        )

    @property
    def script_path(self) -> Path:
        return self.directory / self.manifest.script

    def summary(self) -> dict:
        return {
            "id": self.manifest.skill_id,
            "name": self.manifest.name,
            "version": self.manifest.version,
            "tier": self.manifest.tier,
            "status": self.manifest.status,
            "source": self.manifest.source,
            "legacy": self.legacy,
            "valid": self.valid,
            "errors": list(self.errors),
            "path": str(self.directory),
        }


class SkillRegistry:
    """Discover managed skill tiers and preserve existing agents as legacy skills."""

    def __init__(self, home: Optional[Path | str] = None):
        self.home = Path(home or Path(__file__).resolve().parents[1]).resolve()
        self.skills_root = self.home / "skills"
        self.legacy_root = self.home / "agents"
        self.records: list[SkillRecord] = []
        self.conflicts: list[str] = []

    @property
    def tier_paths(self) -> dict[str, Path]:
        return {tier: self.skills_root / tier for tier in TIERS}

    def ensure_layout(self) -> None:
        for path in self.tier_paths.values():
            path.mkdir(parents=True, exist_ok=True)

    def reload(self) -> list[SkillRecord]:
        self.ensure_layout()
        self.records = []
        self.conflicts = []
        for tier, root in self.tier_paths.items():
            self.records.extend(self._discover_tier(tier, root))
        self.records.extend(self._discover_legacy())
        self._find_trigger_conflicts()
        return list(self.records)

    def list(self, tier: Optional[str] = None) -> list[SkillRecord]:
        if not self.records:
            self.reload()
        return [
            record
            for record in self.records
            if tier is None or record.manifest.tier == tier
        ]

    def get(self, skill_id: str) -> Optional[SkillRecord]:
        for record in self.list():
            if record.manifest.skill_id == skill_id:
                return record
        return None

    def summary(self) -> dict:
        records = self.list()
        return {
            "shared": sum(record.manifest.tier == "shared" for record in records),
            "personal": sum(record.manifest.tier == "personal" for record in records),
            "staging": sum(record.manifest.tier == "staging" for record in records),
            "legacy": sum(record.legacy for record in records),
            "active": sum(record.is_active or record.legacy for record in records),
            "conflicts": list(self.conflicts),
        }

    def load_active_modules(self) -> list[object]:
        modules = []
        for record in self.list():
            if not record.is_active:
                continue
            if not record.script_path.is_file():
                record.valid = False
                record.errors.append(f"script fehlt: {record.manifest.script}")
                continue
            try:
                modules.append(self._load_module(record))
            except Exception as exc:
                record.valid = False
                record.errors.append(str(exc))
        return modules

    def promote(
        self,
        skill_id: str,
        approval_manager=None,
        approval_id: str = "",
    ) -> SkillRecord:
        record = self.get(skill_id)
        if record is None:
            raise ValueError(f"Staging-Skill nicht gefunden: {skill_id}")
        if record.manifest.tier != "staging":
            raise ValueError("Nur Staging-Skills koennen promoted werden.")
        if not record.valid:
            raise ValueError("Ungueltiger Staging-Skill kann nicht aktiviert werden.")
        self._validate_test_paths(record)
        job_id = str(record.manifest.raw.get("job_id") or "").strip()
        if not job_id:
            raise ValueError(
                "Staging-Skills brauchen fuer die Promotion einen erzeugenden job_id."
            )
        if approval_manager is None:
            raise PermissionError("Promotion verlangt eine explizite Freigabe.")
        approval_manager.consume(
            approval_id,
            expected_action="activate_skill",
            expected_job_id=job_id,
        )

        target = self.tier_paths["personal"] / record.directory.name
        if target.exists():
            raise FileExistsError(f"Personal-Skill existiert bereits: {target.name}")
        shutil.move(str(record.directory), str(target))
        manifest_path = target / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["tier"] = "personal"
        data["status"] = "active"
        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.reload()
        promoted = self.get(skill_id)
        if promoted is None:
            raise RuntimeError("Promotion wurde nicht in der Registry gefunden.")
        return promoted

    def _discover_tier(self, tier: str, root: Path) -> list[SkillRecord]:
        records = []
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            manifest_path = directory / "manifest.json"
            if not manifest_path.is_file():
                records.append(self._invalid_record(directory, tier, "manifest.json fehlt"))
                continue
            try:
                manifest = SkillManifest.from_file(manifest_path, tier)
                record = SkillRecord(manifest=manifest, directory=directory)
                if manifest.status == "active" and tier == "staging":
                    record.valid = False
                    record.errors.append("Staging-Skills duerfen nicht aktiv sein.")
                records.append(record)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                records.append(self._invalid_record(directory, tier, str(exc)))
        return records

    def _discover_legacy(self) -> list[SkillRecord]:
        records = []
        if not self.legacy_root.is_dir():
            return records
        for directory in sorted(path for path in self.legacy_root.iterdir() if path.is_dir()):
            script = directory / "script.py"
            if not script.is_file():
                continue
            skill_id = f"legacy-{directory.name.replace('_', '-')}"
            manifest = SkillManifest(
                skill_id=skill_id,
                name=directory.name,
                version="legacy",
                tier="shared",
                description="Bestehender Trinity-Agent mit Legacy-Adapter.",
                triggers=[directory.name],
                allowed_tools=[],
                allowed_paths=[],
                requires_approval=[],
                tests=[],
                status="active",
                source="legacy",
            )
            records.append(SkillRecord(manifest=manifest, directory=directory, legacy=True))
        return records

    def _find_trigger_conflicts(self) -> None:
        owners: dict[str, str] = {}
        for record in self.records:
            if not record.valid or record.legacy:
                continue
            for trigger in record.manifest.triggers:
                normalized = trigger.casefold().strip()
                if not normalized:
                    continue
                previous = owners.setdefault(normalized, record.manifest.skill_id)
                if previous != record.manifest.skill_id:
                    self.conflicts.append(
                        f"Trigger '{trigger}' wird von {previous} und "
                        f"{record.manifest.skill_id} verwendet."
                    )

    def _validate_test_paths(self, record: SkillRecord) -> None:
        missing = [
            test
            for test in record.manifest.tests
            if not (record.directory / test).is_file()
        ]
        if missing:
            raise ValueError(f"Staging-Tests fehlen: {', '.join(missing)}")

    def _invalid_record(self, directory: Path, tier: str, error: str) -> SkillRecord:
        manifest = SkillManifest(
            skill_id=f"invalid-{directory.name.replace('_', '-')}",
            name=directory.name,
            version="unknown",
            tier=tier,
            description="Ungueltiger Skill.",
            triggers=[],
            allowed_tools=[],
            allowed_paths=[],
            requires_approval=[],
            tests=[],
            status="disabled",
        )
        return SkillRecord(manifest=manifest, directory=directory, valid=False, errors=[error])

    @staticmethod
    def _load_module(record: SkillRecord):
        module_name = f"trinity_skill_{record.manifest.skill_id.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, record.script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Skill kann nicht geladen werden: {record.manifest.skill_id}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "can_handle") or not hasattr(module, "execute"):
            raise TypeError("Skill braucht can_handle() und execute().")
        return module


def _string_list(value, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} muss eine Liste von Texten sein.")
    return [item.strip() for item in value if item.strip()]
