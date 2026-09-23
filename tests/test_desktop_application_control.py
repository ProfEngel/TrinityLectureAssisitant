import importlib.util
from pathlib import Path

from desktop_control import DesktopAction, DesktopControlRequest, DesktopControlService
from platform_adapters.desktop_applications import (
    MacOSApplicationController,
    create_application_controller,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "agents"
    / "desktop_control_agent"
    / "script.py"
)


def load_agent():
    spec = importlib.util.spec_from_file_location("test_desktop_control_agent", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_macos_adapter_uses_native_tools_without_shell(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("platform_adapters.desktop_applications.subprocess.run", fake_run)
    controller = MacOSApplicationController()

    controller.open_application("Microsoft Word")
    controller.close_application("Microsoft Word")
    controller.close_application("Finder")

    assert calls[0][0] == ["/usr/bin/open", "-a", "Microsoft Word"]
    assert calls[1][0][0] == "/usr/bin/osascript"
    assert calls[2][0][-1] == 'tell application "Finder" to close every window'
    assert all(call[1].get("shell") is not True for call in calls)
    assert create_application_controller("Darwin").__class__ is MacOSApplicationController
    assert create_application_controller("Windows") is None


def test_service_requires_confirmation_and_writes_audit(tmp_path):
    calls = []

    class FakeController:
        def open_application(self, application):
            calls.append(("open", application))
            return f"{application} wurde geoeffnet."

        def close_application(self, application):
            calls.append(("close", application))
            return f"{application} wurde beendet."

    service = DesktopControlService(
        {
            "enabled": True,
            "dry_run": False,
            "allowed_applications": ["Microsoft Word"],
        },
        controller=FakeController(),
        home=tmp_path,
    )
    request = DesktopControlRequest(DesktopAction.CLOSE_APPLICATION, "Microsoft Word")

    assert service.execute(request).success is False
    assert service.execute(request, confirmed=True).success is True
    assert calls == [("close", "Microsoft Word")]
    audit = tmp_path / "TrinityRuntime" / "audit" / "desktop_control.jsonl"
    assert '"action": "desktop_close_application"' in audit.read_text(encoding="utf-8")


def test_agent_recognizes_only_allowlisted_application_commands():
    agent = load_agent()

    assert agent.can_handle("Trinity, öffne Word")
    assert agent.can_handle("Öffne Open Code")
    assert agent.can_handle("Schließe ChatGPT")
    assert agent.can_handle("Öffne die Mail App")
    assert agent.can_handle("Schließe Finder")
    assert agent.can_handle("Starte Chrome")
    assert not agent.can_handle("Öffne Terminal")
    assert not agent.can_handle("Erkläre mir Microsoft Excel")


def test_agent_opens_and_closes_last_application(tmp_path, monkeypatch):
    agent = load_agent()
    calls = []

    class FakeController:
        def open_application(self, application):
            calls.append(("open", application))
            return f"{application} wurde geoeffnet."

        def close_application(self, application):
            calls.append(("close", application))
            return f"{application} wurde beendet."

    monkeypatch.setattr(agent, "ROOT", tmp_path)
    monkeypatch.setattr(
        agent,
        "LAST_APPLICATION_PATH",
        tmp_path / "TrinityRuntime" / "desktop_control" / "last_application.json",
    )
    monkeypatch.setattr(agent, "create_application_controller", lambda: FakeController())
    context = {
        "full_config": {
            "desktop_control": {
                "enabled": True,
                "dry_run": False,
                "allowed_applications": ["ChatGPT"],
            }
        }
    }

    opened = agent.execute("Öffne ChatGPT", context=context)
    closed = agent.execute("Schließe diese App", context=context)

    assert calls == [("open", "ChatGPT"), ("close", "ChatGPT")]
    assert "geoeffnet" in opened["direct_answer"]
    assert "beendet" in closed["direct_answer"]


def test_agent_respects_disabled_desktop_control(monkeypatch):
    agent = load_agent()
    monkeypatch.setattr(agent, "create_application_controller", lambda: object())

    result = agent.execute(
        "Öffne Word",
        context={"full_config": {"desktop_control": {"enabled": False}}},
    )

    assert "deaktiviert" in result["direct_answer"]
