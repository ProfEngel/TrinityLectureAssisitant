import requests
import json
import os
import subprocess
import shutil
import re
import time
import sys

# Headless core/transcriber.py launches with core/ as sys.path[0]. Agents also
# import sibling agents, so the application root must be available there.
_APPLICATION_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APPLICATION_ROOT not in sys.path:
    sys.path.insert(0, _APPLICATION_ROOT)

from answer_sanitizer import clean_visible_answer
from platform_adapters import capability_message, detect_capabilities
from chat_attachments import prepare_attachment_content
from brainvault_agents import brainvault_root_from_config
from memory_store import MemoryStore
from skill_registry import SkillRegistry
from task_orchestrator import TaskOrchestrator
from lecture_context import add_current_slide
from desktop_context import add_current_desktop
from image_routing import is_image_request, image_skill_allowed
from voice.diagnostics import diagnostic
from media_policy import wants_local_media, wants_song


def reply_token_budget(query, voice_budget):
    """Bound ordinary spoken replies without shortening requested writing work."""
    if not voice_budget:
        return 1500
    detailed = re.search(
        r"ausführlich|ausfuehrlich|detailliert|schritt für schritt|schritt fuer schritt|"
        r"zusammenfass|fass.*zusammen|umschreib|überarbeit|ueberarbeit|formuliere|entwurf|herleitung|"
        r"schreibe|niederschreib", str(query), re.I,
    )
    return 650 if detailed else 320


def build_context_prompt(soul, user, slide_status, search_context, memory_context, transcript, query,
                         desktop_status=""):
    """Keep lecture context available without making every conversation a lecture."""
    slide_status = str(slide_status or "")
    actual_slide = slide_status and not slide_status.startswith("Keine aktuelle Folie")
    asks_about_slide = bool(re.search(r"\b(folie|folien|vortrag|präsentation|praesentation)\b", query, re.I))
    slide_section = (
        f"--- FOLIENKONTEXT (NUR FALLS RELEVANT) ---\n{slide_status}\n\n"
        if actual_slide or asks_about_slide else ""
    )
    asks_about_window = bool(re.search(
        r"\b(fenster|bildschirm|desktop|aktive[nsrm]? programm|siehst du|schau mal|hier)\b",
        query, re.I,
    ))
    desktop_section = (
        f"--- AKTIVES MAC-FENSTER ---\n{desktop_status}\n\n"
        if desktop_status else
        "--- AKTIVES MAC-FENSTER ---\nKein aktuelles Mac-Fenster freigegeben. "
        "Behaupte nicht, den Bildschirm zu sehen. Bitte um Aktivierung der Fensterfreigabe in MiniTrinity.\n\n"
        if asks_about_window else ""
    )
    return (
        f"{soul}\n\n"
        f"--- INFORMATIONEN ZUM NUTZER ---\n{user}\n\n"
        "Trinity ist eine vielseitige persönliche Assistentin für Beruf, Lehre, "
        "Forschung, kreative Projekte und Privatleben. Die aktuelle Frage bestimmt "
        "das Thema. Unterstelle keinen Vorlesungskontext, wenn er nicht erkennbar ist. "
        "Nenne den Namen des Nutzers nur, wenn es sachlich notwendig ist; stelle "
        "dich und deine Hilfsbereitschaft nicht wiederholt vor.\n\n"
        "Bilder, Schaubilder, Infografiken und Diagramme werden ausschließlich "
        "als generierte Rasterbilder über den Bild-Agenten erstellt, niemals "
        "als Mermaid oder Diagramm-Code. Bei nicht verfügbarer Generierung "
        "melde das ehrlich; liefere keinen Code als Ersatzbild.\n\n"
        f"{desktop_section}{slide_section}{search_context}{memory_context}\n\n"
        f"--- LETZTER GESPRÄCHSVERLAUF (NUR ALS KONTEXT) ---\n{transcript}\n\n"
        "Frühere Themen im Verlauf sind nicht automatisch das aktuelle Thema. "
        "Wenn nach früheren Aussagen gefragt wird, beziehe dich genau auf den Verlauf. "
        "Gib niemals interne Reasoning-, Thinking-, Analyse-, Draft-, Check- oder "
        "Self-Correction-Prozesse aus. Antworte nur mit der finalen Nutzerantwort. "
        "Bei kurzen Sprachfragen antworte knapp in höchstens vier Sätzen, sofern "
        "nicht ausdrücklich eine ausführliche Herleitung gewünscht ist."
    )


class TrinityBrain:
    def __init__(self):
        # Konfiguration aus Datei laden
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.soul_path = os.path.join(os.path.dirname(__file__), "Soul.md")
        self.user_path = os.path.join(os.path.dirname(__file__), "User.md")
        self.config = {}
        self._runtime_signature = {}
        self.gen_images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gen_images")
        os.makedirs(self.gen_images_dir, exist_ok=True)
        
        # Gedächtnis für das letzte Bild (für I2I/I2V Folgeanweisungen)
        self.last_media_path = None
        
        self.load_config()

        self.capabilities = detect_capabilities()
        self.live_skills = []
        self.unavailable_skills = []
        self.skill_registry = SkillRegistry(
            os.path.dirname(os.path.dirname(__file__))
        )
        self.task_orchestrator = TaskOrchestrator(
            os.path.dirname(os.path.dirname(__file__))
        )
        self._load_live_skills()

        # Soul + User einmalig laden und cachen (nicht bei jedem Request neu lesen)
        self._soul_cache = self.get_file_content(self.soul_path, "Du bist Trinity, ein KI-Assistent.")
        self._user_cache = self.get_file_content(self.user_path, "Unterstütze den Nutzer ohne Annahmen über seine Identität.")
        self._remember_runtime_signature()

    def load_config(self):
        """Lädt die Konfiguration aus der config.json."""
        try:
            if not os.path.exists(self.config_path):
                print(f"⚠️ config.json nicht gefunden bei {self.config_path}")
                return

            with open(self.config_path, "r") as f:
                config = json.load(f)
            self.config = config
            
            # LLM-Konfiguration (3 Slots Support)
            llm_conf = config.get("llm", {})
            active_slot = llm_conf.get("active_slot", "local")
            
            # Falls noch alte Struktur vorhanden ist (use_local Boolean)
            if "use_local" in llm_conf and "active_slot" not in llm_conf:
                active_slot = "local" if llm_conf["use_local"] else "remote_1"
            
            slot_data = llm_conf.get(active_slot, llm_conf.get("local", {}))
            
            self.url = slot_data.get("url", "")
            self.model = slot_data.get("model", "")
            self.api_key = slot_data.get("api_key", "")
            self.enable_thinking = slot_data.get("enable_thinking")
            if self.enable_thinking is None and active_slot == "local":
                # Lokale Modelle antworten standardmäßig direkt. Das verhindert,
                # dass ein Konfigurations-Update Thinking versehentlich reaktiviert.
                self.enable_thinking = False
            default_timeout = 120 if active_slot == "local" else 90
            try:
                configured_timeout = int(
                    slot_data.get("request_timeout_seconds", default_timeout)
                )
            except (TypeError, ValueError):
                configured_timeout = default_timeout
            # Große lokale Modelle können beim ersten Aufruf länger laden. Das
            # Limit bleibt trotzdem begrenzt, damit ein defekter Provider nicht
            # unbegrenzt die Oberfläche blockiert.
            self.request_timeout_seconds = max(30, min(configured_timeout, 600))
            
            # LM-Studio Fallback für Key wenn leer im lokalen Slot
            if active_slot == "local" and not self.api_key:
                self.api_key = "lm-studio"
            
            apis = config.get("apis", {})
            self.tavily_key = apis.get("tavily", "")
            self.fal_key = apis.get("fal_ai", "")
            self.media_provider = config.get("media_generation", {}).get("provider", "comfyui")
            
            # Persona
            persona = config.get("persona", {})
            self.agent_name = persona.get("agent_name", "Trinity")
            
            # Bild-Modelle (fal.ai)
            image = config.get("image", {})
            self.image_primary = image.get("primary_model", "fal-ai/nano-banana-2")
            self.image_fallback = image.get("fallback_model", "fal-ai/nano-banana-pro")
            
            # ComfyUI-Server (lokaler Tailscale-Node)
            comfyui = config.get("comfyui", {})
            self.comfyui_enabled = comfyui.get("enabled", False)
            self.comfyui_url = comfyui.get("server_url", "")
            self.comfyui_workflow = comfyui.get("default_workflow", "Flux2_Klein_T2I_API.json")
            self.comfyui_music_workflow = comfyui.get("music_workflow", "AceStep1.5_T2A_API.json")
            
            # Telegram-Config (für Skill-Context-Weitergabe)
            self._telegram_cfg = config.get("telegram", {})
            self._codex_cfg = self._with_agent_pool_project(config.get("codex", {}), config)
            self._opencode_cfg = self._with_agent_pool_project(config.get("opencode", {}), config)
            self._pi_cfg = self._with_agent_pool_project(config.get("pi", {}), config)
            
            print("⚙️ Konfiguration geladen ✓")

        except Exception as e:
            print(f"⚠️ Fehler beim Laden der config.json: {e}")

    def _with_agent_pool_project(self, harness_config, full_config):
        """Expose the shared BrainVault pool as a default project for external harnesses."""
        cfg = dict(harness_config or {})
        projects = dict(cfg.get("projects") or {})
        try:
            root = brainvault_root_from_config(
                os.path.dirname(os.path.dirname(__file__)),
                full_config,
            )
        except Exception:
            root = None
        if root and os.path.isdir(root) and os.path.isdir(os.path.join(root, ".agents")):
            projects.setdefault("BrainVault", str(root))
            cfg["default_project"] = "BrainVault"
        cfg["projects"] = projects
        return cfg

    def _file_signature(self, path):
        try:
            stat = os.stat(path)
            return (stat.st_mtime, stat.st_size)
        except OSError:
            return None

    def _current_runtime_signature(self):
        return {
            "config": self._file_signature(getattr(self, "config_path", "")),
            "soul": self._file_signature(getattr(self, "soul_path", "")),
            "user": self._file_signature(getattr(self, "user_path", "")),
        }

    def _remember_runtime_signature(self):
        self._runtime_signature = self._current_runtime_signature()

    def reload_runtime_config(self, force=False):
        """Apply saved settings before the next answer without restarting Trinity."""
        if not getattr(self, "config_path", None):
            return False
        current = self._current_runtime_signature()
        if not force and current == getattr(self, "_runtime_signature", {}):
            return False

        self.load_config()
        self._soul_cache = self.get_file_content(
            self.soul_path,
            "Du bist Trinity, ein KI-Assistent.",
        )
        self._user_cache = self.get_file_content(
            self.user_path,
            "Unterstütze den Nutzer ohne Annahmen über seine Identität.",
        )
        self._runtime_signature = current
        print("🔄 Trinity-Konfiguration für neue Anfrage neu geladen.")
        return True

    def _load_live_skills(self):
        """Load legacy agents plus validated shared/personal managed skills."""
        import importlib.util
        self.live_skills = []
        self.unavailable_skills = []
        agents_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")
        print(f"📂 Suche nach Live-Skills in: {os.path.abspath(agents_dir)}")
        if not os.path.exists(agents_dir):
            return
            
        for item in os.listdir(agents_dir):
            skill_dir = os.path.join(agents_dir, item)
            script_path = os.path.join(skill_dir, "script.py")
            if os.path.isdir(skill_dir) and os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(f"agents.{item}", script_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "can_handle") and hasattr(module, "execute"):
                        required = set(getattr(module, "REQUIRED_CAPABILITIES", set()))
                        missing = required - self.capabilities
                        if missing:
                            self.unavailable_skills.append((module, missing))
                            print(
                                f"⏸️ Skill {item} deaktiviert "
                                f"(fehlend: {', '.join(sorted(missing))})"
                            )
                            continue

                        self.live_skills.append(module)
                        print(f"🔌 Live-Skill geladen: {item}")
                        # Optionaler Init-Hook (z.B. für Index-Vorladung beim Start)
                        if hasattr(module, "init"):
                            module.init()
                except Exception as e:
                    print(f"⚠️ Fehler beim Laden des Skills {item}: {e}")

        # Managed skills are additive. Staging skills are deliberately excluded
        # until their tests and an explicit promotion approval succeeded.
        try:
            for module in self.skill_registry.load_active_modules():
                required = set(getattr(module, "REQUIRED_CAPABILITIES", set()))
                missing = required - self.capabilities
                if missing:
                    self.unavailable_skills.append((module, missing))
                    continue
                self.live_skills.append(module)
                print(f"🔌 Verwalteter Skill geladen: {module.__name__}")
                if hasattr(module, "init"):
                    module.init()
        except Exception as e:
            print(f"⚠️ Fehler beim Laden verwalteter Skills: {e}")

        self.live_skills.sort(
            key=lambda module: getattr(module, "PRIORITY", 0),
            reverse=True,
        )
        self.unavailable_skills.sort(
            key=lambda item: getattr(item[0], "PRIORITY", 0),
            reverse=True,
        )

    def reload_skills(self):
        """Reload only skill metadata/modules; running jobs remain persisted."""
        self.skill_registry.reload()
        self._load_live_skills()
        summary = self.skill_registry.summary()
        print(
            "🔄 Skill-Registry neu geladen: "
            f"{summary['shared']} shared, {summary['personal']} personal, "
            f"{summary['staging']} staging."
        )
        return summary

    def ask_llm(self, messages):
        """Hilfsmethode für interne LLM-Aufrufe (z.B. Context Enrichment)."""
        from core.voice.request_scope import (current_scope, check_cancelled,
                                         interruptible_response, collect_content)
        from voice.sentence_stream import StreamCancelled
        check_cancelled()
        self.reload_runtime_config()
        from sound_deck import SoundDeck
        deck = SoundDeck(os.path.dirname(os.path.dirname(self.config_path)))
        if deck.command(user_query) is not None:
            try:
                deck.execute_voice(user_query)
                return "", False
            except ValueError as exc:
                return str(exc), False
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Trinity Assistant",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0 # Für präzise Fakten/Begriffe
        }
        if getattr(self, "enable_thinking", None) is not None:
            data["enable_thinking"] = bool(self.enable_thinking)
            data["chat_template_kwargs"] = {"enable_thinking": bool(self.enable_thinking)}
        try:
            if current_scope():
                data.update(stream=True, max_tokens=1200)
                with interruptible_response(requests.post(
                    self.url, headers=headers, json=data, stream=True, timeout=(5, 25),
                )) as resp:
                    resp.raise_for_status()
                    return clean_visible_answer(collect_content(resp))
            resp = requests.post(
                self.url,
                headers=headers,
                json=data,
                timeout=getattr(self, "request_timeout_seconds", 90),
            )
            if resp.status_code == 200:
                msg = resp.json()['choices'][0]['message']
                # Qwen3-Fix: Fallback auf reasoning_content wenn content leer
                return clean_visible_answer(
                    msg.get('content') or msg.get('reasoning_content') or ''
                )
        except StreamCancelled:
            raise
        except Exception as e:
            check_cancelled()
            print(f"⚠️ ask_llm Fehler: {e}")
        return ""

    def get_file_content(self, path, fallback=""):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return fallback

    def _is_explicit_local_media_request(self, router_text):
        """Route image edits locally unless the user explicitly requests fal.ai."""
        text = (router_text or "").lower()
        external_markers = [
            "externes bild", "externe grafik", "externes schaubild",
            "bild extern", "grafik extern", "extern erstell", "extern generier",
            "fal.ai", "fal ai",
        ]
        external_media_markers = [
            "bild", "grafik", "schaubild", "infografik", "zeichnung", "illustration",
        ]
        if (
            any(marker in text for marker in external_markers)
            or ("extern" in text and any(marker in text for marker in external_media_markers))
        ):
            return False
        local_markers = [
            "comfyui",
            "flux",
            "lokal",
            "lokales bild",
            "lokal generier",
            "lokal erstell",
            "auf meinem server",
            "auf dem server",
            "render ein",
            "rendere",
        ]
        edit_markers = [
            "bearbeit",
            "änder",
            "aender",
            "anpass",
            "modifizier",
            "verwandle",
            "transform",
            "nimm dieses bild",
            "aus diesem bild",
            "mach daraus",
            "erstelle lokal",
            "generiere lokal",
            "lokal bild",
        ]
        video_markers = ["video", "kurzvideo", "animier", "animation", "i2v", "bewegung"]
        has_local_marker = any(marker in text for marker in local_markers)
        has_edit_marker = any(marker in text for marker in edit_markers + video_markers)
        generation_markers = ["erstell", "erzeug", "generier", "render", "zeichne", "visualisier"]
        image_markers = ["bild", "grafik", "schaubild", "infografik", "zeichnung", "illustration"]
        has_generation_request = (
            any(marker in text for marker in generation_markers)
            and any(marker in text for marker in image_markers)
        )
        return has_edit_marker or (has_local_marker and has_generation_request)

    def _skill_allowed_for_image_upload(self, skill, router_text):
        """Avoid hijacking normal image understanding with generation agents."""
        if is_image_request(router_text):
            return image_skill_allowed(skill, router_text, getattr(self, "media_provider", "comfyui"))
        module_name = getattr(skill, "__name__", "")
        if module_name.endswith("comfyui_agent") or "comfyui_agent" in module_name:
            return self._is_explicit_local_media_request(router_text)
        if module_name.endswith("image_agent") or "image_agent" in module_name:
            return False
        return True

    @staticmethod
    def _skill_label(skill):
        return getattr(skill, "__name__", getattr(skill, "__file__", "Skill"))

    def _skill_can_handle(self, skill, router_text, skill_context=None):
        if is_image_request(router_text):
            return image_skill_allowed(skill, router_text, getattr(self, "media_provider", "comfyui"))
        try:
            handles_query = bool(skill.can_handle(router_text))
        except Exception as exc:
            print(
                "⚠️ Skill-Erkennung übersprungen "
                f"({self._skill_label(skill)}): {exc}"
            )
            return False

        if (
            not handles_query
            and skill_context is not None
            and hasattr(skill, "can_handle_with_context")
        ):
            try:
                handles_query = bool(
                    skill.can_handle_with_context(router_text, skill_context)
                )
            except Exception as exc:
                print(
                    "⚠️ Kontext-Skill-Erkennung übersprungen "
                    f"({self._skill_label(skill)}): {exc}"
                )
                return False
        return handles_query

    def _skill_can_handle_song(self, skill, router_text):
        if is_image_request(router_text):
            return False
        if getattr(self, "media_provider", "comfyui") == "kie":
            expected = "comfyui_agent" if wants_local_media(router_text) else "kie_media_agent"
            if expected not in self._skill_label(skill):
                return False
        if not hasattr(skill, "can_handle_song"):
            return False
        try:
            return bool(skill.can_handle_song(router_text))
        except Exception as exc:
            print(
                "⚠️ Song-Skill-Erkennung übersprungen "
                f"({self._skill_label(skill)}): {exc}"
            )
            return False


    def _execute_media_skill(self, execute, query, context):
        home = os.path.dirname(os.path.dirname(getattr(self, "config_path", __file__)))
        context = dict(context)
        if getattr(self, "config", {}).get("media_generation", {}).get("background_jobs"):
            from media_jobs import start_media_job
            return start_media_job(home, query, execute, context)
        return self._run_media_skill(execute, query, context)

    def _run_media_skill(self, execute, query, context):
        home = os.path.dirname(os.path.dirname(getattr(self, "config_path", __file__)))
        diagnostic(home, "Media", "started")
        try:
            result = execute(query, context=context)
            if (not result.get("has_payload") and result.get("fallback_safe") is True
                    and getattr(self, "config", {}).get("media_generation", {}).get("comfyui_fallback")
                    and "kie_media_agent" in getattr(execute, "__module__", "")):
                from agents.comfyui_agent import script as comfy
                result = (comfy.execute_t2a if wants_song(query) else comfy.execute)(query, context=context)
                if result.get("has_payload"):
                    result["direct_answer"] = "Das Medium ist fertig. kie.ai war nicht verfügbar; ComfyUI hat lokal übernommen."
            return result
        finally:
            diagnostic(home, "Media", "finished")

    def get_soul(self):
        return self._soul_cache

    def get_user(self):
        return self._user_cache

    def read_transcript(self, transcript_file):
        try:
            with open(transcript_file, "r") as f:
                lines = f.readlines()
                # Nur die letzten 30 Zeilen nehmen, um Tokens zu sparen
                return "".join(lines[-30:])[-8000:]
        except FileNotFoundError:
            return "Noch kein Transkript vorhanden."

    def ask(
        self,
        user_query,
        transcript_file,
        text_mode=False,
        action_text=None,
        from_telegram=False,
        attachments=None,
        voice_budget=False,
        desktop_image_available=None,
        sentence_callback=None,
        cancelled=lambda: False,
    ):
        from core.voice.request_scope import check_cancelled, interruptible_response
        from voice.sentence_stream import StreamCancelled
        check_cancelled()
        self.reload_runtime_config()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost", # Required by OpenRouter
            "X-Title": "Trinity Assistant", # Required by OpenRouter
            "Content-Type": "application/json"
        }
        
        transcript = self.read_transcript(transcript_file)
        soul_prompt = self.get_soul()
        user_prompt = self.get_user()
        attachment_content = prepare_attachment_content(user_query, attachments or [])
        slide_image = False
        desktop_image = False
        if getattr(self, "config_path", None):
            home = os.path.dirname(os.path.dirname(self.config_path))
            if desktop_image_available is not False:
                desktop_image = add_current_desktop(attachment_content, home, query=user_query)
            if not desktop_image:
                slide_image = add_current_slide(attachment_content, home)
        primary_image_path = attachment_content["primary_image_path"]
        if primary_image_path:
            self.last_media_path = primary_image_path
        if attachments:
            kinds = ", ".join(
                str(item.get("kind") or "file") for item in attachments
            )
            print(f"📎 Anlagen empfangen: {len(attachments)} ({kinds})")
        if primary_image_path:
            print(f"🖼️ Bildanlage für Vision-Modell vorbereitet: {primary_image_path}")
        
        # Agentic Router
        search_context = ""
        has_payload = False
        direct_answer = ""
        
        # action_text = letzten 2-3 Chunks (für präzise Keyword-Erkennung)
        # user_query = voller Kontext (alle 8 Chunks, für LLM-Verständnis)
        router_text = (action_text or user_query).lower()
        lower_query = user_query.lower()
        task_decision = None
        orchestrator = getattr(self, "task_orchestrator", None)
        if orchestrator is not None:
            try:
                task_decision = orchestrator.prepare(
                    action_text or user_query,
                    source="telegram" if from_telegram else ("chat" if text_mode else "speech"),
                )
                if task_decision.blocked:
                    job_id = (task_decision.job or {}).get("job_id", "")
                    approval_id = (task_decision.approval or {}).get("approval_id", "")
                    message = task_decision.message or "Der Auftrag braucht eine Freigabe."
                    if approval_id:
                        message += (
                            f" Freigabe {approval_id} fuer Job {job_id} wurde lokal angelegt; "
                            "es wurde noch nichts ausgefuehrt."
                        )
                    return message, False
                if task_decision.job:
                    print(
                        "📋 Trinity-Plan angelegt: "
                        f"{task_decision.job['job_id']} ({task_decision.route})"
                    )
            except Exception as exc:
                print(f"⚠️ Job-Planung nicht verfuegbar: {exc}")

        for skill, missing in getattr(self, "unavailable_skills", []):
            if self._skill_can_handle(skill, router_text):
                search_context = (
                    "--- FUNKTION NICHT VERFÜGBAR ---\n"
                    f"{capability_message(missing)}\n\n"
                )
                break
        
        # --- DYNAMIC SKILL DISPATCH ---
        # --- COMFYUI SONG DISPATCH (T2A) ---
        # Wird vor dem normalen Skill-Loop geprüft, da Song-Trigger spezifisch sind
        for skill in getattr(self, 'live_skills', []):
            if search_context:
                break
            if self._skill_can_handle_song(skill, router_text):
                try:
                    result = self._execute_media_skill(skill.execute_t2a, user_query, {
                        "brain": self,
                        "from_telegram": from_telegram,
                        "telegram_cfg": getattr(self, '_telegram_cfg', {}),
                        "codex_cfg": getattr(self, '_codex_cfg', {}),
                        "opencode_cfg": getattr(self, '_opencode_cfg', {}),
                        "pi_cfg": getattr(self, '_pi_cfg', {}),
                        "full_config": getattr(self, "config", {}),
                        "image_path": primary_image_path,
                        "attachments": attachments or [],
                        "task_decision": task_decision,
                    })
                    check_cancelled()
                    if result.get("has_payload"):
                        payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                        with open(payload_path, "w", encoding="utf-8") as f:
                            f.write(result.get("html_payload", ""))
                        has_payload = True
                    search_context = result.get("search_context", search_context)
                    direct_answer = result.get("direct_answer", direct_answer)
                except StreamCancelled:
                    raise
                except Exception as e:
                    check_cancelled()
                    print(f"⚠️ Fehler bei T2A-Skill: {e}")
                break  # Kein weiterer Skill nötig

        # --- DYNAMIC SKILL DISPATCH (T2I / I2I / alle anderen) ---
        if not has_payload and not search_context:
            for skill in getattr(self, 'live_skills', []):
                skill_context = {
                    "brain": self,
                    "from_telegram": from_telegram,
                    "telegram_cfg": getattr(self, '_telegram_cfg', {}),
                    "codex_cfg": getattr(self, '_codex_cfg', {}),
                    "opencode_cfg": getattr(self, '_opencode_cfg', {}),
                    "pi_cfg": getattr(self, '_pi_cfg', {}),
                    "full_config": getattr(self, "config", {}),
                    "image_path": primary_image_path,
                    "attachments": attachments or [],
                    "task_decision": task_decision,
                }
                if (primary_image_path or slide_image or desktop_image) and not self._skill_allowed_for_image_upload(skill, router_text):
                    print(
                        f"🖼️ Überspringe {getattr(skill, '__name__', 'Skill')} "
                        "für normale Bildanalyse."
                    )
                    continue
                handles_query = self._skill_can_handle(
                    skill,
                    router_text,
                    skill_context,
                )
                if handles_query:
                    try:
                        if is_image_request(router_text):
                            result = self._execute_media_skill(skill.execute, user_query, skill_context)
                        else:
                            result = skill.execute(user_query, context=skill_context)
                        check_cancelled()
                        if result.get("has_payload"):
                            payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                            with open(payload_path, "w", encoding="utf-8") as f:
                                f.write(result.get("html_payload", ""))
                            has_payload = True
                        # search_context: Kontext vom Skill (Web, RAG, etc.) – nur einmal verwenden
                        search_context = result.get("search_context", search_context)
                        direct_answer = result.get("direct_answer", direct_answer)
                    except StreamCancelled:
                        raise
                    except Exception as e:
                        check_cancelled()
                        print(f"⚠️ Fehler bei der Skill-Ausführung: {e}")
                    break

        # An image request must terminate here: no LLM-generated Mermaid, HTML
        # diagram, or implicit cloud fallback when the raster generator fails.
        if is_image_request(router_text):
            direct_answer = direct_answer or (
                "Das generierte Bild ist fertig und im Medien-Player verfügbar."
                if has_payload else
                "Es wurde kein Bild erstellt. " + (search_context.strip() or
                "Die Bildgenerierung ist derzeit nicht verfügbar. Bitte später erneut versuchen.")
            )
        elif getattr(self, "media_provider", "comfyui") == "kie":
            from agents.kie_media_agent.script import can_handle_song
            if can_handle_song(router_text) and not direct_answer:
                direct_answer = "Es wurde kein Lied erstellt. " + (search_context.strip() or "Die Musikgenerierung ist derzeit nicht verfügbar.")

        check_cancelled()
        if direct_answer:
            direct_answer = clean_visible_answer(direct_answer)
            if orchestrator is not None:
                orchestrator.finish(task_decision, direct_answer)
            return direct_answer, has_payload

        try:
            memory_context = MemoryStore().context_for_prompt(user_query)
        except Exception as exc:
            print(f"⚠️ Memory-Kontext nicht verfügbar: {exc}")
            memory_context = ""

        context_prompt = build_context_prompt(
            soul_prompt, user_prompt, attachment_content.get("lecture_status", ""),
            search_context, memory_context, transcript, user_query,
            desktop_status=attachment_content.get("desktop_status", ""),
        )

        data = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": reply_token_budget(user_query, voice_budget),
            "messages": [
                {"role": "system", "content": context_prompt},
                {"role": "user", "content": attachment_content["content"]}
            ]
        }
        if getattr(self, "enable_thinking", None) is not None:
            data["enable_thinking"] = bool(self.enable_thinking)
            # LMStudio / Qwen3: benötigt zusätzlich chat_template_kwargs
            data["chat_template_kwargs"] = {"enable_thinking": bool(self.enable_thinking)}
        
        try:
            print(f"🧠 Trinity denkt nach über: '{user_query}'...")
            if sentence_callback is not None:
                from voice.sentence_stream import stream_sentences, StreamCancelled
                data["stream"] = True
                with interruptible_response(requests.post(self.url, headers=headers, json=data, stream=True,
                                   timeout=(5, 25))) as streamed:
                    if streamed.status_code >= 400 and (primary_image_path or slide_image or desktop_image):
                        streamed.close()
                        data["messages"][-1]["content"] = attachment_content["fallback_text"]
                        data["messages"][0]["content"] += "\nACHTUNG: Kein Bild verfügbar; nutze nur Text und benenne die Einschränkung."
                        with interruptible_response(requests.post(self.url, headers=headers, json=data, stream=True,
                                           timeout=(5, 25))) as fallback:
                            fallback.raise_for_status()
                            answer = stream_sentences(fallback, sentence_callback, cancelled)
                    else:
                        streamed.raise_for_status()
                        answer = stream_sentences(streamed, sentence_callback, cancelled)
                if orchestrator is not None:
                    check_cancelled()
                    orchestrator.finish(task_decision, answer)
                return answer, has_payload
            response = requests.post(
                self.url,
                headers=headers,
                json=data,
                timeout=(5, 25) if voice_budget else getattr(self, "request_timeout_seconds", 90),
            )
            if response.status_code >= 400 and (primary_image_path or slide_image or desktop_image):
                print(
                    "⚠️ Das aktive Modell hat die Bildeingabe abgelehnt. "
                    "Wiederhole die Anfrage mit Dateikontext ohne Bilddaten."
                )
                data["messages"][-1]["content"] = attachment_content["fallback_text"]
                data["messages"][0]["content"] += "\nACHTUNG: Der Bildrequest wurde abgelehnt. In dieser Wiederholung ist KEIN Bild verfügbar. Nutze nur Text und benenne diese Einschränkung."
                response = requests.post(
                    self.url,
                    headers=headers,
                    json=data,
                    timeout=(5, 25) if voice_budget else getattr(self, "request_timeout_seconds", 90),
                )
            response.raise_for_status()
            check_cancelled()
            
            result = response.json()
            msg = result['choices'][0]['message']
            # Qwen3-Fix: Im Thinking-Modus ist 'content' leer, Antwort steht in 'reasoning_content'
            answer = clean_visible_answer(
                msg.get('content') or msg.get('reasoning_content') or ''
            )
            print(f"💡 Antwort ({len(answer)} Zeichen): {answer[:80]}...")
            
            # Falls Textmodus aktiv ist und noch kein Payload gesetzt wurde (z.B. keine Map), erzeuge Untertitel-Payload
            if text_mode and not has_payload:
                formatted_answer = answer.replace('\n', '<br>')
                # Mit KEEP_OPEN, damit das Fenster offen bleibt, bis der User es explizit schließt
                html_payload = f"""
                <!-- KEEP_OPEN -->
                <!-- TEXT_RESPONSE_PAYLOAD -->
                <h2 style="margin-top: 0; font-weight: 300; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px; font-size: 18px;">Antwort</h2>
                <div style="font-size: 16px; line-height: 1.5; opacity: 0.9;">
                    {formatted_answer}
                </div>
                """
                payload_path = os.path.join(os.path.dirname(__file__), "payload.html")
                with open(payload_path, "w", encoding="utf-8") as f:
                    f.write(html_payload)
                has_payload = True

            if orchestrator is not None:
                orchestrator.finish(task_decision, answer)
            return answer, has_payload
            
        except Exception as e:
            from voice.sentence_stream import StreamCancelled
            if isinstance(e, StreamCancelled):
                raise
            if sentence_callback is not None:
                # Once audio started, never replace the answer with a fallback
                # and persist it as though it were the spoken response.
                raise
            print(f"Fehler bei der Kommunikation mit dem Gehirn: {e}")
            if orchestrator is not None:
                orchestrator.finish(
                    task_decision,
                    str(e),
                    succeeded=False,
                )
            if isinstance(e, requests.exceptions.Timeout):
                return "Das eingestellte Modell hat nicht rechtzeitig geantwortet. Ich konnte die Anfrage nicht auswerten.", False
            if isinstance(e, requests.exceptions.ConnectionError):
                return "Ich erreiche das eingestellte Modell gerade nicht. Bitte prüfe die Modellverbindung.", False
            return "Die Modellanfrage ist fehlgeschlagen. Ich konnte den Inhalt nicht zuverlässig auswerten.", False

if __name__ == "__main__":
    # Kalttest-Skript
    brain = TrinityBrain()
    antwort, _ = brain.ask("Erkläre in einem Satz, was ein autonomer Agent ist.", "memory/test.md")
    print(f"Antwort: {antwort}")
