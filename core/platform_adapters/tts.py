import os
import platform
import shutil
import subprocess
from typing import List, Optional


class SilentProcess:
    """Popen-compatible no-op used when no TTS backend is available."""

    returncode = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class TTSBackend:
    name = "unavailable"

    def is_available(self) -> bool:
        return False

    def speak(self, text: str, voice: str = "", output_device: str = "Standard"):
        print(f"Sprachausgabe nicht verfügbar: {text}")
        return SilentProcess()

    def list_voices(self) -> List[str]:
        return []

    def list_output_devices(self) -> List[str]:
        return ["Standard"]


class MacOSTTSBackend(TTSBackend):
    name = "macOS say"

    def is_available(self) -> bool:
        return shutil.which("say") is not None

    def speak(self, text: str, voice: str = "", output_device: str = "Standard"):
        if not self.is_available():
            return super().speak(text, voice, output_device)

        command = ["say"]
        if voice:
            command.extend(["-v", voice])

        if output_device and output_device != "Standard":
            device_id = self._device_id(output_device)
            if device_id:
                command.extend(["-a", device_id])

        command.append(text)
        return subprocess.Popen(command)

    def list_voices(self) -> List[str]:
        try:
            output = subprocess.check_output(
                ["say", "-v", "?"], stderr=subprocess.STDOUT, text=True
            )
        except (OSError, subprocess.SubprocessError):
            return []

        voices = []
        for line in output.splitlines():
            name = line.strip().split(maxsplit=1)[0] if line.strip() else ""
            if name and name not in voices:
                voices.append(name)
        return voices

    def list_output_devices(self) -> List[str]:
        try:
            output = subprocess.check_output(
                ["say", "-a", "?"], stderr=subprocess.STDOUT, text=True
            )
        except (OSError, subprocess.SubprocessError):
            return ["Standard"]

        devices = ["Standard"]
        for line in output.splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) == 2 and parts[1] not in devices:
                devices.append(parts[1])
        return devices

    def _device_id(self, device_name: str) -> Optional[str]:
        try:
            output = subprocess.check_output(
                ["say", "-a", "?"], stderr=subprocess.STDOUT, text=True
            )
        except (OSError, subprocess.SubprocessError):
            return None

        for line in output.splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) == 2 and parts[1] == device_name:
                return parts[0]
        return None


class WindowsTTSBackend(TTSBackend):
    name = "Windows SAPI"

    _SPEAK_SCRIPT = r"""
$voice = New-Object -ComObject SAPI.SpVoice
$requestedVoice = $env:TRINITY_TTS_VOICE
if ($requestedVoice) {
    foreach ($token in @($voice.GetVoices())) {
        if ($token.GetDescription() -like "*$requestedVoice*") {
            $voice.Voice = $token
            break
        }
    }
}
$requestedOutput = $env:TRINITY_TTS_OUTPUT
if ($requestedOutput -and $requestedOutput -ne "Standard") {
    foreach ($output in @($voice.GetAudioOutputs())) {
        if ($output.GetDescription() -eq $requestedOutput) {
            $voice.AudioOutput = $output
            break
        }
    }
}
[void]$voice.Speak($env:TRINITY_TTS_TEXT)
"""

    def __init__(self):
        self.executable = shutil.which("powershell.exe") or shutil.which("powershell")

    def is_available(self) -> bool:
        return self.executable is not None

    def speak(self, text: str, voice: str = "", output_device: str = "Standard"):
        if not self.is_available():
            return super().speak(text, voice, output_device)

        environment = os.environ.copy()
        environment["TRINITY_TTS_TEXT"] = text
        environment["TRINITY_TTS_VOICE"] = voice
        environment["TRINITY_TTS_OUTPUT"] = output_device or "Standard"
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        return subprocess.Popen(
            [
                self.executable,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                self._SPEAK_SCRIPT,
            ],
            env=environment,
            creationflags=creation_flags,
        )

    def list_voices(self) -> List[str]:
        return self._run_descriptions(
            "$v=New-Object -ComObject SAPI.SpVoice;"
            "@($v.GetVoices()) | ForEach-Object {$_.GetDescription()}"
        )

    def list_output_devices(self) -> List[str]:
        descriptions = self._run_descriptions(
            "$v=New-Object -ComObject SAPI.SpVoice;"
            "@($v.GetAudioOutputs()) | ForEach-Object {$_.GetDescription()}"
        )
        return ["Standard", *[item for item in descriptions if item != "Standard"]]

    def _run_descriptions(self, script: str) -> List[str]:
        if not self.is_available():
            return []
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return []

        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def create_tts_backend(system: Optional[str] = None) -> TTSBackend:
    system_name = system or platform.system()
    if system_name == "Darwin":
        return MacOSTTSBackend()
    if system_name == "Windows":
        return WindowsTTSBackend()
    return TTSBackend()
