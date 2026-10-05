"""Conservative source/release hygiene gate. Reports locations, never values.

This is a pattern check, not proof that every possible secret was discovered.
Run before committing and again on an extracted release archive. It does not
rewrite history or inspect the user's ignored runtime configuration.
"""
import argparse
from pathlib import Path
import re
import subprocess


RULES = {
    "private Tailnet IP": re.compile(r"100\.\d+\.\d+\.\d+"),
    "personal runtime path": re.compile(r'''/(?:Users|home)/(?!your-user|USERNAME|NAME|demo|example)[^/\s"']+/(?:Projects|Trinity|AppData)'''),
    "Tavily credential": re.compile(r"tvly-(?:dev-)?[A-Za-z0-9_-]{20,}"),
    "API credential": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
    "hex credential": re.compile(r'''(?i)(?:api.?key|token|password|passwort)["']?\s*[:=]\s*["'][a-f0-9]{32,}["']'''),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def audit(root, archive=False):
    if archive:
        files = sorted(p for p in root.rglob("*") if p.is_file())
    else:
        output = subprocess.check_output([
            "git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"
        ], cwd=root)
        files = sorted(set(root / name.decode() for name in output.split(b"\0") if name))
    problems = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if (relative in {"core/config.json", "core/Soul.md", "core/User.md", ".env"}
                or any(part in {"TrinityRuntime", "logs", "gen_images", "venv", ".venv"}
                       for part in Path(relative).parts)
                or path.suffix in {".sqlite", ".sqlite3", ".db", ".mobileprovision", ".p12"}
                or relative.endswith(".bak")):
            problems.append((relative, 0, "runtime or credential file"))
        if not path.exists() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".heic", ".mp4", ".wav"}:
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        for number, line in enumerate(contents.splitlines(), 1):
            # This scanner necessarily describes the personal-path regex.
            if path.name == "audit_release.py":
                continue
            for label, pattern in RULES.items():
                if pattern.search(line):
                    problems.append((relative, number, label))
    for relative, number, label in problems:
        print(f"{relative}:{number}: {label}")
    print(f"Hygiene check: {len(files)} files, {len(problems)} findings. No secret values printed.")
    return not problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if audit(Path(args.root).resolve(), args.archive) else 1)
