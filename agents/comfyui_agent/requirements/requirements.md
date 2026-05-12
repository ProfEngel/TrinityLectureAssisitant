# ComfyUI Agent Requirements

Dieses Dokument beschreibt die Hardware- und Software-Voraussetzungen sowie die notwendigen Modelle für den Betrieb der Trinity ComfyUI-Integration.

## 🖥️ Hardware-Anforderungen

Für den reibungslosen Betrieb der generativen Workflows (insbesondere Video und Flux) wird eine leistungsstarke Workstation benötigt:

*   **Betriebssystem:** Linux (empfohlen) oder Windows 10/11.
*   **Grafikkarte (GPU):** Dedizierte NVIDIA-GPU mit CUDA-Support.
*   **VRAM:** Mindestens **12 GB VRAM** erforderlich.
    *   *Beispiel:* NVIDIA RTX 4070 (12 GB) oder besser.
*   **RAM:** Mindestens 32 GB Systemspeicher empfohlen.

## ⚙️ Software-Voraussetzungen

1.  **ComfyUI:** Die aktuellste Version von [ComfyUI](https://github.com/comfyanonymous/ComfyUI) muss installiert sein.
2.  **Server-Modus:** ComfyUI muss über das Netzwerk erreichbar sein. Wenn Trinity auf einem anderen Gerät läuft als der ComfyUI-Server, muss die `server_url` in den Trinity-Einstellungen korrekt gesetzt werden.
3.  **Netzwerk (Tailscale):** Falls der Server über das Internet erreichbar sein muss, wird die Nutzung von [Tailscale](https://tailscale.com/) empfohlen. Damit lässt sich ein sicheres, privates Netzwerk (VPN) über das Internet aufbauen, ohne Ports im Router freigeben zu müssen.
4.  **Custom Nodes:** Folgende Custom Nodes müssen in ComfyUI installiert sein (via ComfyUI Manager):
    *   `rgthree-comfy`
    *   `ComfyUI-Video-Helper-Suite` (VHS)
    *   `ComfyUI-GGUF`
    *   `ComfyUI-KJNodes`
    *   `ComfyUI-Custom-Scripts` (pysssss)

## 🧠 Modell-Installation

Alle Modelle können über [Huggingface](https://huggingface.co/) bezogen werden. Es werden vorwiegend **quantisierte Modelle** (GGUF oder FP8) verwendet, um den VRAM-Verbrauch zu optimieren und den Betrieb auf Consumer-Hardware zu ermöglichen.

Speichere die Modelle in den entsprechenden Unterordnern deines `ComfyUI/models/`-Ordners:

### 1. Flux.2 (Text-to-Image & Image-to-Image)
*   **Modell (UNET):** `flux-2-klein-9b-fp8.safetensors` ➔ `models/unet/`
*   **CLIP/T5:** `qwen_3_8b_fp8mixed.safetensors` ➔ `models/clip/`
*   **VAE:** `flux2-vae.safetensors` ➔ `models/vae/`

### 2. AceStep 1.5 (Text-to-Audio / Song-Generierung)
*   **Modell (UNET):** `acestep_v1.5_xl_turbo_bf16.safetensors` ➔ `models/unet/`
*   **CLIPs:** `qwen_0.6b_ace15.safetensors` & `qwen_1.7b_ace15.safetensors` ➔ `models/clip/`
*   **VAE:** `ace_1.5_vae.safetensors` ➔ `models/vae/`

### 3. LTX 2.3 (Image-to-Video)
*   **Modell (UNET GGUF):** `ltx-2.3-22b-distilled-Q4_K_M.gguf` ➔ `models/unet/`
*   **LoRA:** `ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors` ➔ `models/loras/ltx2.3/`
*   **CLIPs:** `gemma-3-12b-it-qat-UD-Q4_K_XL.gguf` & `ltx-2.3-22b-dev_embeddings_connectors.safetensors` ➔ `models/clip/`
*   **VAEs:**
    *   `ltx-2.3-22b-dev_audio_vae.safetensors` ➔ `models/vae/`
    *   `ltx-2.3-22b-dev_video_vae.safetensors` ➔ `models/vae/`
    *   `taeltx2_3.safetensors` ➔ `models/vae/`
*   **Upscaler:** `ltx-2.3-spatial-upscaler-x2-1.0.safetensors` ➔ `models/upscale_models/`

---
*Hinweis: Trinity nutzt die API-Schnittstelle von ComfyUI. Stelle sicher, dass die Dateinamen der Modelle exakt mit den oben genannten (bzw. den in den JSON-Workflows hinterlegten) Namen übereinstimmen.*
