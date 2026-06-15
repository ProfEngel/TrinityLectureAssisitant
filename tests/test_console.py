import builtins

import trinity_console


class _FakeRuntime:
    def __init__(self):
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class _CaptureFile:
    def __init__(self):
        self.content = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def write(self, value):
        self.content += value


def test_terminal_cli_writes_silent_commands_and_exits_cleanly(monkeypatch):
    runtime = _FakeRuntime()
    commands = iter(["Status prüfen", "exit"])
    capture = _CaptureFile()

    def fake_input(_prompt):
        try:
            return next(commands)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr(trinity_console.subprocess, "Popen", lambda _args: runtime)
    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: capture)

    return_code = trinity_console.run_console("unused-runtime.py")

    assert capture.content == "SILENT:Status prüfen"
    assert runtime.terminated is True
    assert return_code == 0
