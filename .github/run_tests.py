"""Bound collection, execution and Qt shutdown; retain output on CI failures."""
import pathlib
import subprocess
import sys


groups = {
    "backend": ["--ignore=tests/test_avatar_tray.py", "--ignore=tests/test_desktop_speaker_control.py"],
    "avatar": ["tests/test_avatar_tray.py"],
    "speaker": ["tests/test_desktop_speaker_control.py"],
}
failed = False
for name, selection in groups.items():
    log = pathlib.Path(f"test-{name}.log")
    print(f"Starting {name}", flush=True)
    bootstrap = (
        "import faulthandler,pytest; "
        "faulthandler.dump_traceback_later(60); "
        "raise SystemExit(pytest.main())"
    )
    command = [sys.executable, "-u", "-c", bootstrap, "-vv",
               "--timeout=45", "--timeout-method=thread",
               f"--junitxml=test-{name}.xml", *selection]
    try:
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                    timeout=120, check=False)
        failed |= result.returncode != 0
    except subprocess.TimeoutExpired:
        failed = True
        print(f"{name}: exceeded 120 seconds", flush=True)
    finally:
        print(log.read_text(encoding="utf-8", errors="replace")[-16000:], flush=True)
raise SystemExit(1 if failed else 0)
