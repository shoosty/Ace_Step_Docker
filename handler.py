import runpod
import sys
import os
import base64
import tempfile
import traceback
import time
import os

sys.path.insert(0, '/ace-step-code')

# Wait for volume to mount
checkpoint = "/workspace/models/acestep-v15-turbo"
for i in range(30):
    if os.path.exists(checkpoint):
        break
    print(f"Waiting for volume... {i}")
    time.sleep(2)

from acestep.pipeline_ace_step import ACEStepPipeline

print("Loading ACE-Step pipeline...")
pipe = ACEStepPipeline(
    checkpoint_dir="/workspace/models/acestep-v15-turbo",
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
