"""ACE-Step v33 — 1.5 XL with proper handler architecture.

Uses the new AceStepHandler + LLMHandler split introduced in 1.5.
Models live at /runpod-volume/checkpoints/ (symlinked from /models).
"""
import runpod
import sys
import os
import base64
import tempfile
import traceback
import subprocess
import shutil
import time
import uuid
import urllib.request

sys.path.insert(0, '/ace-step-code')

MODEL_SIZE = os.environ.get("MODEL_SIZE", "xl").lower()

CHECKPOINTS_DIR = "/runpod-volume/checkpoints"
if not os.path.exists(CHECKPOINTS_DIR):
    raise RuntimeError(f"Checkpoints not found at {CHECKPOINTS_DIR}")

dit_variant = "acestep-v15-xl-base" if MODEL_SIZE == "xl" else "acestep-v15-turbo"
lm_variant = "acestep-5Hz-lm-1.7B"

os.environ["ACESTEP_CHECKPOINTS_DIR"] = CHECKPOINTS_DIR

print(f"Loading ACE-Step 1.5 (DiT={dit_variant}, LM={lm_variant})...")

from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

dit_handler = AceStepHandler()
llm_handler = LLMHandler()

dit_handler.initialize_service(
    project_root="/runpod-volume",
    config_path=dit_variant,
    device="cuda",
)

llm_handler.initialize(
    checkpoint_dir=CHECKPOINTS_DIR,
    lm_model_path=lm_variant,
    backend="vllm",
    device="cuda",
)

print("Pipeline loaded!")

if not shutil.which("ffmpeg"):
    print("WARNING: ffmpeg not on PATH — MP3 conversion will fall back to WAV.")

# ── Supabase client ────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
ACESTEP_BUCKET = os.environ.get("ACESTEP_BUCKET", "song-uploads")

_supabase_client = None
def supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
    from supabase import create_client
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client

def wav_to_mp3(wav_path: str, mp3_path: str, bitrate: str = "192k") -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
         "-codec:a", "libmp3lame", "-b:a", bitrate, mp3_path],
        check=True,
    )

def upload_to_supabase(local_path: str, storage_path: str, content_type: str) -> str:
    sb = supabase_client()
    with open(local_path, "rb") as f:
        data = f.read()
    sb.storage.from_(ACESTEP_BUCKET).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    res = sb.storage.from_(ACESTEP_BUCKET).get_public_url(storage_path)
    if isinstance(res, dict):
        return res.get("publicUrl") or res.get("publicURL") or res.get("public_url")
    return res

def download_to_temp(url: str, suffix: str = ".bin") -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        local_path = f.name
    urllib.request.urlretrieve(url, local_path)
    return local_path

def handler(job):
    """RunPod serverless entrypoint."""
    src_temp = None
    lora_temp = None
    try:
        inp = job.get("input", {}) or {}

        caption  = inp.get("caption", "pop music")
        lyrics   = inp.get("lyrics",  "[Instrumental]")
        duration = float(inp.get("audio_duration", inp.get("duration", 30)))

        fmt = (inp.get("format") or "mp3").lower()
        if fmt not in ("mp3", "wav"):
            return {"error": f"format must be 'mp3' or 'wav', got '{fmt}'"}
        keep_wav   = bool(inp.get("keep_wav", False)) and fmt == "mp3"
        return_b64 = bool(inp.get("return_audio_b64", False))

        ts       = int(time.time())
        short_id = uuid.uuid4().hex[:12]
        storage_path = inp.get("storage_path") or f"acestep-runs/{ts}-{short_id}.{fmt}"
        if not storage_path.endswith(f".{fmt}"):
            base, _, _ = storage_path.rpartition(".")
            storage_path = f"{base or storage_path}.{fmt}"
        storage_path_wav = inp.get("storage_path_wav")
        if keep_wav and not storage_path_wav:
            base, _, _ = storage_path.rpartition(".")
            storage_path_wav = f"{base}-wav.wav"

        # LoRA on-demand
        lora_url = inp.get("lora_url")
        if lora_url:
            lora_temp = download_to_temp(lora_url, suffix=".safetensors")

        # Build params for 1.5
        params = GenerationParams(
            caption=caption,
            duration=duration,
        )
        if inp.get("lyrics"):
            params.lyrics = lyrics
        if lora_temp:
            params.lora_path = lora_temp
            params.lora_weight = float(inp.get("lora_weight", 1.0))
        if inp.get("manual_seeds"):
            params.seed = int(inp["manual_seeds"][0]) if isinstance(inp["manual_seeds"], list) else int(inp["manual_seeds"])

        config = GenerationConfig(
            batch_size=1,
            audio_format="wav",
        )

        with tempfile.TemporaryDirectory() as save_dir:
            result = generate_music(dit_handler, llm_handler, params, config, save_dir=save_dir)
            if hasattr(result, "audio_paths") and result.audio_paths:
            wav_path = result.audio_paths[0]
        elif hasattr(result, "audio_path"):
            wav_path = result.audio_path
        elif hasattr(result, "output_path"):
            wav_path = result.output_path
        elif hasattr(result, "save_paths") and result.save_paths:
            wav_path = result.save_paths[0]
else:
    import glob
    wavs = glob.glob(f"{save_dir}/*.wav") + glob.glob(f"{save_dir}/*.flac")
    if not wavs:
        return {"error": f"No audio found. Result attrs: {dir(result)}"}
    wav_path = wavs[0]

            mp3_path = None
            if fmt == "mp3":
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    mp3_path = f.name
                wav_to_mp3(wav_path, mp3_path)
                primary_local = mp3_path
                primary_ct = "audio/mpeg"
            else:
                primary_local = wav_path
                primary_ct = "audio/wav"

            audio_url = upload_to_supabase(primary_local, storage_path, primary_ct)

            resp = {
                "audio_url": audio_url,
                "format": fmt,
                "storage_path": storage_path,
                "duration": duration,
                "task": "text2music",
            }

            if keep_wav:
                wav_url = upload_to_supabase(wav_path, storage_path_wav, "audio/wav")
                resp["wav_url"] = wav_url
                resp["wav_storage_path"] = storage_path_wav

            if return_b64:
                with open(primary_local, "rb") as f:
                    resp["audio_b64"] = base64.b64encode(f.read()).decode("utf-8")

            if mp3_path and os.path.exists(mp3_path):
                try: os.unlink(mp3_path)
                except: pass

            return resp

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}
    finally:
        if src_temp and os.path.exists(src_temp):
            try: os.unlink(src_temp)
            except: pass
        if lora_temp and os.path.exists(lora_temp):
            try: os.unlink(lora_temp)
            except: pass

runpod.serverless.start({"handler": handler})
