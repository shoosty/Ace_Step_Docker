import runpod
import sys
import os
import base64
import tempfile
import traceback
import time

sys.path.insert(0, '/ace-step-code')

# Verify models exist - fail fast if not found
checkpoint = "/workspace/models/models--ACE-Step--ACE-Step-v1-3.5B/snapshots/82cd0d7b6322bd28cd4e830fe675ddb6180ce36c"
if not os.path.exists(checkpoint):
    raise RuntimeError(f"Models not found at {checkpoint} - check volume mount!")

print(f"Models found at {checkpoint}")

from acestep.pipeline_ace_step import ACEStepPipeline

print("Loading ACE-Step pipeline...")
pipe = ACEStepPipeline(
    checkpoint_dir=checkpoint,
    dtype="bfloat16"
)
print("Pipeline loaded!")

def handler(job):
    try:
        inp = job["input"]
        caption = inp.get("caption", "pop music")
        lyrics = inp.get("lyrics", "[Instrumental]")
        duration = inp.get("duration", 30)
        lora_url = inp.get("lora_url", None)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = f.name
        pipe(audio_duration=duration, prompt=caption, lyrics=lyrics, save_path=output_path)
        with open(output_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        os.unlink(output_path)
        return {"audio_b64": audio_b64}
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

runpod.serverless.start({"handler": handler})
