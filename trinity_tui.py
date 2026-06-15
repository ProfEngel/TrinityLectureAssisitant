"""Terminal chat and slash-command interface for Trinity."""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path


def _load_core(home):
    core_dir = str(Path(home) / "core")
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    from configuration import load_config, save_config  # pylint: disable=import-outside-toplevel
    from memory_store import MemoryStore  # pylint: disable=import-outside-toplevel

    return load_config, save_config, MemoryStore


def _format_session(row):
    title = row.get("title") or "Trinity Session"
    summary = row.get("summary") or ""
    suffix = f" · {summary[:70]}" if summary else ""
    return f"{row['id']} · {title}{suffix}"


def _print_block(title, body=""):
    print(f"\n{title}")
    print("=" * len(title))
    if body:
        print(body)


class TrinityTui:
    def __init__(self, home, session_id=None, input_fn=input, output_fn=print):
        self.home = Path(home)
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.load_config, self.save_config, MemoryStore = _load_core(self.home)
        self.store = MemoryStore(self.home / "memory" / "trinity_memory.sqlite3")
        self.session_id = self.store.ensure_session(
            session_id or "tui",
            "Trinity TUI",
        )
        self.transcript_path = self.home / "memory" / "tui_transcript.md"
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        self._brain = None

    def emit(self, text=""):
        self.output_fn(text)

    def _lazy_brain(self):
        if self._brain is None:
            core_dir = str(self.home / "core")
            if core_dir not in sys.path:
                sys.path.insert(0, core_dir)
            from brain import TrinityBrain  # pylint: disable=import-outside-toplevel

            self._brain = TrinityBrain()
        return self._brain

    def run(self):
        _print_block(
            "Trinity TUI",
            "Schreibe direkt an Trinity oder nutze /help. Beenden mit /exit.",
        )
        self.print_status()
        while True:
            try:
                raw = self.input_fn("\ntrinity> ")
            except (EOFError, KeyboardInterrupt):
                self.emit("\nTUI beendet.")
                return 0
            if not raw.strip():
                continue
            try:
                if raw.strip().startswith("/"):
                    result = self.handle_command(raw.strip())
                    if result == "exit":
                        return 0
                    continue
                self.chat(raw.strip())
            except Exception as exc:  # pragma: no cover - defensive terminal guard
                self.emit(f"Fehler: {exc}")

    def print_status(self):
        status = self.store.status()
        self.emit(
            f"Session {self.session_id} · "
            f"{status['memories']} Memories · {status['links']} Links"
        )

    def handle_command(self, raw_command):
        parts = shlex.split(raw_command[1:])
        command = parts[0].casefold() if parts else "help"
        args = parts[1:]

        if command in {"help", "?"}:
            self.emit(command_help())
            return None
        if command in {"exit", "quit", "q"}:
            self.emit("TUI beendet.")
            return "exit"
        if command in {"status", "usage"}:
            self.print_status()
            return None
        if command in {"models", "model"}:
            self.handle_model(command, args)
            return None
        if command == "session":
            self.handle_session(args)
            return None
        if command in {"context", "compress"}:
            result = self.store.compress_context(self.session_id)
            if result["compressed"]:
                self.emit(f"Kontext verdichtet: {result['compressed']} ältere Nachrichten.")
            else:
                self.emit("Noch nicht genug Verlauf für eine Kompression.")
            return None
        if command == "remember":
            text, tags = self._split_text_and_tags(args)
            if not text:
                self.emit("Nutze: /remember <Text> --tags tag1,tag2")
                return None
            memory_id = self.store.remember(
                text,
                tags,
                source="tui",
                session_id=self.session_id,
                weight=0.68,
            )
            self.emit(f"Gespeichert: {memory_id[:8]}")
            return None
        if command == "memory":
            self.handle_memory(args)
            return None
        if command == "graph":
            graph = self.store.graph_data()
            self.emit(
                f"Memory Graph: {len(graph['nodes'])} Knoten, {len(graph['links'])} Links."
            )
            return None
        if command == "settings":
            self.emit("Einstellungen: nutze `trinity settings` oder `trinity settings --gui`.")
            return None
        if command == "doctor":
            self.emit("Diagnose: nutze `trinity doctor` oder `trinity doctor --fix`.")
            return None

        self.emit(f"Unbekannter Befehl: /{command}. Nutze /help.")
        return None

    def _split_text_and_tags(self, args):
        if "--tags" not in args:
            return " ".join(args).strip(), []
        index = args.index("--tags")
        text = " ".join(args[:index]).strip()
        tag_text = " ".join(args[index + 1 :]).strip()
        tags = [tag.strip() for tag in tag_text.split(",") if tag.strip()]
        return text, tags

    def handle_model(self, command, args):
        config_path = self.home / "core" / "config.json"
        config = self.load_config(config_path)
        llm = config.setdefault("llm", {})
        active = llm.get("active_slot", "local")
        if command == "models" or not args:
            lines = []
            for slot, data in llm.items():
                if not isinstance(data, dict):
                    continue
                marker = "*" if slot == active else " "
                lines.append(
                    f"{marker} {slot}: {data.get('model', '')} · {data.get('url', '')}"
                )
            self.emit("\n".join(lines) or "Keine Modelle konfiguriert.")
            return

        slot = args[0]
        if slot not in llm or not isinstance(llm[slot], dict):
            self.emit(f"Unbekannter Provider-Slot: {slot}")
            return
        llm["active_slot"] = slot
        if len(args) > 1:
            llm[slot]["model"] = " ".join(args[1:])
        self.save_config(config_path, config)
        model = llm[slot].get("model", "")
        self.emit(f"Aktives Modell: {slot} · {model}")

    def handle_session(self, args):
        action = args[0].casefold() if args else "show"
        if action in {"show", "current"}:
            self.emit(f"Aktuelle Session: {self.session_id}")
            return
        if action in {"new", "start"}:
            title = " ".join(args[1:]).strip() or "Trinity TUI"
            self.session_id = self.store.create_session(title)
            self.emit(f"Neue Session: {self.session_id} · {title}")
            return
        if action in {"list", "ls"}:
            sessions = self.store.list_sessions()
            self.emit("\n".join(_format_session(row) for row in sessions) or "Keine Sessions.")
            return
        if action in {"resume", "use"}:
            if len(args) < 2:
                self.emit("Nutze: /session resume <id>")
                return
            self.session_id = self.store.ensure_session(args[1], "Trinity TUI")
            self.emit(f"Session aktiv: {self.session_id}")
            return
        self.emit("Nutze: /session, /session new, /session list, /session resume <id>")

    def handle_memory(self, args):
        action = args[0].casefold() if args else "status"
        if action == "status":
            status = self.store.status()
            rooms = ", ".join(f"{item['room']}:{item['count']}" for item in status["rooms"])
            self.emit(
                f"{status['memories']} Memories, {status['unbaked']} unbaked, "
                f"{status['links']} Links. Tags: {rooms or 'keine'}"
            )
            return
        if action == "search":
            query = " ".join(args[1:])
            results = self.store.search(query, limit=8)
            if not results:
                self.emit("Keine passenden Memories gefunden.")
                return
            self.emit(
                "\n".join(
                    f"- {item['summary']} [{', '.join(item.get('tags') or [])}]"
                    for item in results
                )
            )
            return
        if action == "bake":
            imported = self.store.bake_chat_history()
            self.emit(
                f"Memory Bake: {imported['imported']} importiert, "
                f"{imported['baked']} gebacken, {imported['summaries']} Verdichtungen."
            )
            return
        if action == "dream":
            result = self.store.dream_tick()
            self.emit(f"Dreaming: {result['links_created']} neue/erkannte Links.")
            return
        self.emit("Nutze: /memory status, /memory search <Text>, /memory bake, /memory dream")

    def chat(self, text):
        self.store.add_message(self.session_id, "user", text, {"source": "tui"})
        memory_context = self.store.context_for_prompt(text)
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## User\n{text}\n")
            if memory_context:
                handle.write(f"\n{memory_context}\n")

        prompt = f"{memory_context}\n\n{text}" if memory_context else text
        answer, _has_payload = self._lazy_brain().ask(
            prompt,
            str(self.transcript_path),
            text_mode=True,
        )
        self.store.add_message(self.session_id, "assistant", answer, {"source": "tui"})
        self.store.remember(
            f"User: {text}\nTrinity: {answer}",
            source="tui-chat",
            session_id=self.session_id,
            weight=0.57,
        )
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## Trinity\n{answer}\n")
        self.emit(f"\nTrinity: {answer}")


def command_help():
    return """Verfügbare Befehle
/help                         Hilfe anzeigen
/models                       Provider-Slots und Modelle anzeigen
/model <slot> [modell]        Provider-Slot wechseln, optional Modell setzen
/session                      Aktuelle Session anzeigen
/session new [titel]          Neue Session starten
/session list                 Sessions auflisten
/session resume <id>          Session fortsetzen
/context oder /compress       Älteren Verlauf als Memory verdichten
/remember <text> --tags a,b   Wissen manuell speichern
/memory status                Memory-Status anzeigen
/memory search <text>         Memory durchsuchen
/memory bake                  Classic-Chat importieren und self-baken
/memory dream                 Tags gewichten und Links bilden
/graph                        Graph-Kennzahlen anzeigen
/settings                     Hinweis auf Settings-CLI
/doctor                       Hinweis auf Doctor
/exit                         Beenden"""


def run_tui(home, args=None):
    args = args or argparse.Namespace(session=None)
    return TrinityTui(home, session_id=getattr(args, "session", None)).run()

