FROM --platform=linux/amd64 runpod/base:0.6.2-cuda12.1.0

# ACE-Step 1.5 XL — v36
# Supports MODEL_SIZE env var: "2b" or "xl" (default: xl)

RUN apt-get update && apt-get install -y python3.11 python3.11-dev git curl ffmpeg && \
    curl https://bootstrap.pypa.io/get-pip.py | python3.11 && \
    apt-get clean

RUN mkdir /ace-step-code && \
    git clone https://github.com/ace-step/ACE-Step-1.5.git /ace-step-code

RUN pip3.11 install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu121 && \
    pip3.11 install -e /ace-step-code --no-deps && \
    pip3.11 install fsspec jinja2 networkx sympy setuptools \
        diffusers "transformers>=4.55.0" accelerate peft soundfile \
        librosa loguru tqdm numpy click datasets==3.4.1 \
        pytorch_lightning==2.5.1 pypinyin num2words py3langid \
        hangul-romanize spacy thinc hf_transfer \
        runpod torchcodec typing_extensions \
        supabase && \
    pip3.11 install "click>=8.0"

RUN mkdir -p /app
COPY handler.py /app/handler.py

CMD ["python3.11", "/app/handler.py"]
