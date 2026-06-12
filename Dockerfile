FROM --platform=linux/amd64 runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# ACE-Step 1.5 XL — v49
# Universal CUDA 12.8 — supports RTX 4090, 5090, A100, H100

RUN apt-get update && apt-get install -y git curl ffmpeg && apt-get clean

RUN mkdir /ace-step-code && \
    git clone https://github.com/ace-step/ACE-Step-1.5.git /ace-step-code

RUN pip install -e /ace-step-code --no-deps && \
    pip install fsspec jinja2 networkx sympy setuptools \
        diffusers "transformers>=4.51.0,<4.58.0" accelerate peft soundfile \
        librosa loguru tqdm numpy click "datasets==3.4.1" \
        "pytorch_lightning==2.5.1" pypinyin num2words py3langid \
        hangul-romanize spacy thinc hf_transfer \
        einops "vector_quantize_pytorch>=1.27.15" \
        runpod torchcodec typing_extensions \
        supabase && \
    pip install "click>=8.0"

RUN mkdir -p /app
COPY handler.py /app/handler.py

CMD ["python", "/app/handler.py"]
