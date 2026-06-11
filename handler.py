"""ACE-Step v31 — URL-returning handler with LoRA-on-demand support.

Stephen 2026-06-11 updates:
  - Added lora_url support — handler downloads LoRA from Supabase
    URL on-demand instead of requiring local volume copies. Keeps
    LoRA library in one source of truth, instantly synced across
    all regional endpoints.

Required env vars on the worker:
  SUPABASE_URL              — https://<project>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY — service-role JWT
  ACESTEP_BUCKET (optional) — default "song-uploads"
  MODEL_SIZE (optional)     — "2b" or "xl" (default: "xl")

CRITICAL: RunPod serverless mounts network volumes at /runpod-volume,
NOT /workspace. Every path here uses /runpod-volume/.
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

if MODEL_SIZE == "xl":
    checkpoint = "/runpod-volume/models/acestep-v15-base"
else:
    checkpoint = "/runpod-volume/models/acestep-v15-turbo"

if not os.path.exists(checkpoint):
    raise RuntimeError(f"Models not found at {checkpoint} - check volume mount!")

print(f"Models found at {checkpoint} (MODEL_SIZE={MODEL_SIZE})")

from acestep.pipeline_ace_step import ACEStepPipeline

print("Loading ACE-Step 1.5 pipeline...")
pipe = ACEStepPipeline(
    checkpoint_dir=checkpoint,
    dtype="bfloat16"
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
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set "
            "on this RunPod endpoint for URL-based uploads."
        )
    from supabase import create_client
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client

PIPELINE_KWARGS = [
    "audio_duration",
    "infer_step",
    "guidance_scale",
    "scheduler_type",
    "cfg_type",
    "omega_scale",
    "manual_seeds",
    "guidance_interval",
    "guidance_interval_decay",
    "min_guidance_scale",
    "use_erg_tag",
    "use_erg_lyric",
    "use_erg_diffusion",
    "oss_steps",
    "guidance_scale_text",
    "guidance_scale_lyric",
    "audio2audio_enable",
    "ref_audio_strength",
    "ref_audio_input",
    "lora_name_or_path",
    "lora_weight",
    "retake_seeds",
    "retake_variance",
    "task",
    "repaint_start",
    "repaint_end",
    "src_audio_path",
    "edit_target_prompt",
    "edit_target_lyrics",
    "edit_n_min",
    "edit_n_max",
    "edit_n_avg",
    "batch_size",
    "debug",
]

def wav_to_mp3(wav_path: str, mp3_path: str, bitrate: str = "192k") -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", wav_path,
            "-codec:a", "libmp3lame",
            "-b:a", bitrate,
            mp3_path,
        ],
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
    """RunPod serverless entrypoint.

    Inputs:
      caption, lyrics, duration, format, keep_wav, src_audio_url,
      lora_url, lora_weight, return_audio_b64, storage_path
      + all PIPELINE_KWARGS pass-through.

    LoRA on-demand:
      Pass lora_url pointing to a Supabase storage URL. Handler
      downloads the LoRA to a temp path and feeds it to the
      pipeline. Cleaned up after the job completes.
    """
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

        kwargs = {"audio_duration": duration}
        for key in PIPELINE_KWARGS:
            if key == "audio_duration":
                continue
            if key in inp and inp[key] is not None:
                kwargs[key] = inp[key]

        src_audio_url = inp.get("src_audio_url")
        if src_audio_url:
            suffix = ".wav"
            if "." in src_audio_url.split("/")[-1]:
                suffix = "." + src_audio_url.rsplit(".", 1)[1].split("?")[0][:5]
            src_temp = download_to_temp(src_audio_url, suffix=suffix)
            kwargs["src_audio_path"] = src_temp
            if kwargs.get("task") == "audio2audio":
                kwargs.setdefault("ref_audio_input", src_temp)
                kwargs.setdefault("audio2audio_enable", True)

        # LoRA on-demand download
        lora_url = inp.get("lora_url")
        if lora_url:
            lora_temp = download_to_temp(lora_url, suffix=".safetensors")
            kwargs["lora_name_or_path"] = lora_temp
            if "lora_weight" not in kwargs:
                kwargs["lora_weight"] = inp.get("lora_weight", 1.0)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        mp3_path = None
        try:
            pipe(
                prompt=caption,
                lyrics=lyrics,
                save_path=wav_path,
                **kwargs,
            )

            if fmt == "mp3":
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    mp3_path = f.name
                wav_to_mp3(wav_path, mp3_path)
                primary_local = mp3_path
                primary_ct    = "audio/mpeg"
            else:
                primary_local = wav_path
                primary_ct    = "audio/wav"

            audio_url = upload_to_supabase(primary_local, storage_path, primary_ct)

            resp = {
                "audio_url":    audio_url,
                "format":       fmt,
                "storage_path": storage_path,
                "duration":     duration,
                "task":         kwargs.get("task", "text2music"),
            }

            if keep_wav:
                wav_url = upload_to_supabase(wav_path, storage_path_wav, "audio/wav")
                resp["wav_url"]          = wav_url
                resp["wav_storage_path"] = storage_path_wav

            if return_b64:
                with open(primary_local, "rb") as f:
                    resp["audio_b64"] = base64.b64encode(f.read()).decode("utf-8")

            return resp

        finally:
            for p in (wav_path, mp3_path):
                if p and os.path.exists(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}
    finally:
        if src_temp and os.path.exists(src_temp):
            try:
                os.unlink(src_temp)
            except OSError:
                pass
        if lora_temp and os.path.exists(lora_temp):
            try:
                os.unlink(lora_temp)
            except OSError:
                pass

runpod.serverless.start({"handler": handler})
