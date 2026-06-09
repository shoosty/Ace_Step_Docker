# ACE-Step v29 deploy notes

What v29 ships:

1. **URL response** — handler uploads to Supabase and returns `audio_url`. No more base64 in the response, no more RunPod 10 MB cap on long songs (the v28 stuck-row bug).
2. **MP3 + WAV** — `format: "mp3"` (default, 192 kbps) returns a small MP3 fast. Pass `keep_wav: true` to also upload the lossless WAV alongside; the response includes `wav_url`. Studio calls this on the initial generation so "I'm happy, download lossless" works without a re-render.
3. **Full pipeline pass-through** — every `ACEStepPipeline.__call__` kwarg is whitelist-forwarded from `event["input"]`. Including `task` (text2music | retake | repaint | extend | edit | audio2audio), `lora_name_or_path` + `lora_weight` (the moat), `manual_seeds`, `retake_seeds`, `retake_variance`, `repaint_start/end`, `edit_target_prompt/lyrics`, `audio2audio_enable`, `ref_audio_strength`, `infer_step`, `guidance_scale`, `scheduler_type`, `cfg_type`, etc. See the `PIPELINE_KWARGS` list at the top of `handler.py`.
4. **Remote source audio** — pass `src_audio_url` instead of `src_audio_path` when the worker doesn't have local access to the file (repaint / edit / audio2audio / remaster modes). The handler downloads it to a temp file before calling ACE-Step.
5. **ffmpeg** — added to the Dockerfile for the WAV→MP3 transcode.

## Build + push

```bash
cd ~/Ace_Step_Docker
git pull
docker build --platform linux/amd64 -t shoosty1/ace-step:v29 .
docker push shoosty1/ace-step:v29
```

## RunPod env vars (REQUIRED)

The handler refuses jobs that don't have these set, with a clear error in the response so it's not a mystery:

| Var | Value |
|---|---|
| `SUPABASE_URL` | `https://sgqlpcvbwgsjkllppfna.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | service-role JWT from Supabase Dashboard → Settings → API |
| `ACESTEP_BUCKET` (optional) | default `song-uploads` |

## RunPod endpoint update

RunPod console → endpoint `pd2iixy9kh509f` → New Release → `shoosty1/ace-step:v29`. Confirm a smoke test from `/test-music`. Expect a small response payload with `audio_url` (a `studio.shoosty.com` storage URL) instead of a base64 blob.

## What this enables in the studio (already wired)

- Production `/api/start-generation` ACE-Step branch now sends `format: "mp3"`, `keep_wav: true`, and explicit `storage_path` so files land at `<song_id>/<gen_id>.mp3` and `.wav`.
- `/api/generation-status` reads `audio_url` from `output.audio_url` (no decode, no upload). Falls back to the old base64 path if it sees v28 output.
- `/api/cron/recover-stuck-generations` and `/api/admin/rescue-generation` both URL-aware too.

## What's still queued (handler is ready; studio side TBD)

- **"Download WAV" button** on song detail — read `comet_response.wav_url`, render a link.
- **Retake button** — submit with `task: "retake"`, fresh `retake_seeds`, low `retake_variance`.
- **Repaint UI** — select a region of lyrics → submit with `task: "repaint"`, `repaint_start`, `repaint_end`, and `src_audio_url` pointing at the original take's `wav_url`.
- **Remaster button** — submit with `task: "audio2audio"`, `src_audio_url = original wav_url`, low `ref_audio_strength` (0.1-0.3) for "clean it up without changing it."
- **LoRA picker** — pass `lora_name_or_path` (HuggingFace ID or storage URL) and `lora_weight`.
- **Stems via LoRA pair** — submit two extra jobs alongside the main one: same prompt + `manual_seeds`, with Lyric2Vocal LoRA → vocal stem, Text2Samples LoRA → instrumental stem. Wait for upstream `StemGen` to swap to native.

## Note on the v28 stuck rows

Dadbot and any other v28 jobs that completed at RunPod but never returned to us are **unrecoverable**. The audio was generated but RunPod discarded the worker's response when it busted the 10 MB cap. Once v29 is live, re-run those songs — the new path will work end-to-end.
