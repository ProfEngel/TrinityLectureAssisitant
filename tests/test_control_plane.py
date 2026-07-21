import json

from control_plane import TrinityControlPlane
from harness_adapters import BuilderHarnessAdapter, HarnessJobRequest, ScriptWorkflowAdapter
from trinity_paths import TrinityPaths, default_runtime_root, default_vault_root


def test_trinity_paths_create_separated_runtime_and_vault(tmp_path):
    runtime = tmp_path / "runtime"
    vault = tmp_path / "BrainVault"
    config = {
        "control_plane": {
            "runtime_root": str(runtime),
            "vault_root": str(vault),
        }
    }

    paths = TrinityPaths.from_config(tmp_path, config)
    summary = paths.ensure_layout()

    assert summary["runtime_root"] == str(runtime.resolve())
    assert summary["vault_root"] == str(vault.resolve())
    assert (runtime / "jobs" / "queue").is_dir()
    assert (runtime / "harnesses" / "codex").is_dir()
    assert (runtime / "memory").is_dir()
    assert not (vault / "00_registry").exists()
    assert not (vault / "01_agents").exists()
    assert not any("innerhalb" in warning for warning in summary["warnings"])


def test_platform_defaults_keep_runtime_local_and_vault_syncable(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert default_runtime_root("Windows").as_posix().endswith(
        "localappdata/Trinity/TrinityRuntime"
    )
    assert default_vault_root("Windows").as_posix().endswith(
        "BrainVault"
    )
    assert default_runtime_root("Linux").as_posix().endswith(
        "xdg/trinity/TrinityRuntime"
    )


def test_control_plane_initializes_vault_catalog_and_adapters(tmp_path):
    runtime = tmp_path / "TrinityRuntime"
    vault = tmp_path / "BrainVault"
    agents_root = tmp_path / "LocalAgentPool"
    config = {
        "control_plane": {
            "runtime_root": str(runtime),
            "vault_root": str(vault),
            "external_agents_root": str(agents_root),
        }
    }

    result = TrinityControlPlane(tmp_path, config).ensure_foundation()
    catalog_path = runtime / "catalog" / "agent_catalog.json"

    assert catalog_path.is_file()
    assert (runtime / "policies" / "default_policy.json").is_file()
    assert (runtime / "model_profiles" / "local-default.json").is_file()
    assert (runtime / "artifacts" / "artifact_index.jsonl").is_file()
    assert (runtime / "memory" / "jobs.sqlite3").is_file()
    assert not (vault / ".agents").exists()
    assert (agents_root / ".agents").is_dir()
    assert (agents_root / ".agents" / "_meta" / "agent_catalog.json").is_file()
    assert not (vault / "00_registry").exists()
    assert not (vault / "03_results").exists()
    assert not (vault / ".catalog").exists()
    assert not (vault / ".ai").exists()
    assert result["adapters"]["script-workflow"]["ok"] is True
    assert result["adapters"]["builder"]["ok"] is True

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["schema_version"] == 2
    assert "agents" in catalog
    by_id = {agent["agent_id"]: agent for agent in catalog["agents"]}
    assert by_id["trinity-core"]["quality_status"] == "stable"
    assert "allowed_tools" in by_id["trinity-core"]


def test_control_plane_registers_artifacts_in_vault(tmp_path):
    runtime = tmp_path / "TrinityRuntime"
    vault = tmp_path / "BrainVault"
    config = {"control_plane": {"runtime_root": str(runtime), "vault_root": str(vault)}}
    plane = TrinityControlPlane(tmp_path, config)
    plane.ensure_foundation()

    record = plane.register_artifact(
        "job_123",
        "image",
        "Schaubild Notation",
        source_path="/tmp/schaubild.png",
        metadata={"topic": "Notation"},
    )

    assert record["kind"] == "image"
    assert record["title"] == "Schaubild Notation"
    assert plane.artifacts.list()[0]["artifact_id"] == record["artifact_id"]


def test_script_workflow_adapter_runs_registered_workflow():
    def workflow(request):
        return {
            "summary": f"Hallo {request.inputs['name']}",
            "artifacts": [{"kind": "text", "title": "Begruessung"}],
        }

    adapter = ScriptWorkflowAdapter({"hello": workflow})
    handle = adapter.start_job(
        HarnessJobRequest(
            agent_id="hello",
            title="Test",
            inputs={"name": "Trinity"},
        )
    )

    assert handle.status == "completed"
    assert adapter.get_job_status(handle.job_id).message == "Hallo Trinity"
    assert adapter.collect_artifacts(handle.job_id)[0].title == "Begruessung"


def test_builder_harness_creates_reviewable_capability_request():
    adapter = BuilderHarnessAdapter()
    handle = adapter.start_job(
        HarnessJobRequest(
            agent_id="agent-builder",
            title="Mail-Agent verbessern",
            prompt="Bitte einen sicheren Mail-Agenten entwerfen.",
            mode="development",
        )
    )

    artifacts = adapter.collect_artifacts(handle.job_id)

    assert handle.status == "completed"
    assert artifacts[0].kind == "capability_request"
    assert artifacts[0].metadata["mode"] == "development"
    assert artifacts[0].metadata["next_steps"][0] == "Agentenvertrag erstellen"
