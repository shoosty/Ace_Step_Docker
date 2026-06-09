# ACE-Step RunPod Serverless — Setup & Operations Guide

## Status: WORKING ✅
**Solved June 9, 2026 — after 4 days**

---

## Working Configuration

| Item | Value |
|------|-------|
| Endpoint ID | `pd2iixy9kh509f` |
| Endpoint Name | Ace-step-18 |
| Docker Image | `shoosty1/ace-step:v28` |
| GitHub Repo | `https://github.com/shoosty/Ace_Step_Docker` |
| Docker Hub | `shoosty1/ace-step` |
| Network Volume | `voiceless_emerald_vulture` (US-NC-1) |
| Volume Mount | `/runpod-volume` (NOT /workspace!) |
| Python Version | 3.10 |
| Base Image | `runpod/base:0.6.2-cuda12.1.0` |

---

## The Root Cause (Why It Took 4 Days)

RunPod serverless mounts network volumes at `/runpod-volume` — NOT `/workspace`.

Every version before v28 was pointing to `/workspace/models/...` which doesn't exist in serverless containers. The volume is only accessible at `/runpod-volume/`.

This caused the handler to silently fall back to downloading models from HuggingFace on every cold start, causing timeouts.

---

## Model Path
