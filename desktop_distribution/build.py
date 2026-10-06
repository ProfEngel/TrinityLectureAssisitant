"""Build a small native bootstrapper with a clean, audited source payload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.19.1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, ROOT / "tools/audit_release.py", ROOT], check=True)
    stage = Path(tempfile.mkdtemp(prefix="trinity-package-"))
    resources = stage / "resources"
    resources.mkdir()
    # git archive uses committed files only: never capture the running desktop.
    source = resources / "source.zip"
    subprocess.run(["git", "archive", "--format=zip", "HEAD", "-o", str(source)], cwd=ROOT, check=True)
    (resources / "source.sha256").write_text(hashlib.sha256(source.read_bytes()).hexdigest())
    import uv
    binary = Path(uv.find_uv_bin())
    shutil.copyfile(binary, resources / binary.name)
    if os.name != "nt":
        (resources / binary.name).chmod(0o755)
    shutil.copyfile(ROOT / "assets/trinity_icon_new.png", resources / "icon.png")
    for src, name in [("assets/voices/eve/initial.wav", "eve.wav"), ("assets/voices/eve/initial.txt", "eve.txt")]:
        if (ROOT / src).is_file():
            shutil.copyfile(ROOT / src, resources / name)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
               "--name", "Trinity", "--distpath", str(output), "--workpath", str(stage / "work"),
               "--specpath", str(stage), "--add-data", f"{resources}{os.pathsep}resources",
               "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtWebEngineWidgets",
               "--exclude-module", "torch", "--exclude-module", "numpy"]
    if sys.platform == "darwin":
        command += ["--icon", str(ROOT / "assets/trinity_icon.icns"), "--osx-bundle-identifier", "de.trinity.desktop"]
    command.append(str(ROOT / "desktop_distribution/first_run.py"))
    subprocess.run(command, check=True)
    if sys.platform == "darwin":
        import plistlib
        plist = output / "Trinity.app/Contents/Info.plist"
        info = plistlib.loads(plist.read_bytes())
        info.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION,
                    NSMicrophoneUsageDescription="Trinity verwendet das Mikrofon für Deine freigegebene Spracheingabe.",
                    NSAppleEventsUsageDescription="Trinity kann nach Deiner Freigabe in aktiven Apps beim Schreiben helfen.")
        plist.write_bytes(plistlib.dumps(info))
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(output / "Trinity.app")], check=True)
        dmg = output / f"Trinity-{VERSION}-macOS-arm64.dmg"
        dmg_stage = stage / "dmg"
        dmg_stage.mkdir()
        shutil.copytree(output / "Trinity.app", dmg_stage / "Trinity.app", symlinks=True)
        (dmg_stage / "Applications").symlink_to("/Applications")
        subprocess.run(["hdiutil", "create", "-volname", "Trinity Desktop", "-srcfolder", str(dmg_stage),
                        "-ov", "-format", "UDZO", str(dmg)], check=True)
        artifacts = [dmg]
    else:
        archive = output / f"Trinity-{VERSION}-Windows-x64-portable.zip"
        shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=output / "Trinity")
        artifacts = [archive]
        # Inno Setup supplied by the Windows build runner; no admin install.
        compiler = shutil.which("ISCC.exe") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        subprocess.run([compiler, f"/DSourceDir={output / 'Trinity'}", f"/DOutputDir={output}",
                        str(ROOT / "desktop_distribution/windows.iss")], check=True)
        artifacts.append(output / f"Trinity-{VERSION}-Windows-x64-Setup.exe")
    (output / f"SHA256SUMS-{sys.platform}.txt").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts
    ))
    (output / "build-info.json").write_text(json.dumps({"version": VERSION, "commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "python": sys.version, "platform": sys.platform}, indent=2))


if __name__ == "__main__":
    main()
