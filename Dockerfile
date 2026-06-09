FROM runpod/base:0.6.2-cuda12.1.0

# ffmpeg added 2026-06-09 (v29): handler now converts WAV → MP3
# before base64-encoding the response. Raw WAVs were busting
# RunPod's 10MB response cap on songs over ~30s. MP3 at 192kbps
# is ~6× smaller — a 4-min song comes back as ~8MB base64,
# comfortably under the cap.
RUN apt-get update && apt-get install -y python3.10 git curl ffmpeg && \
    curl https://bootstrap.pypa.io/get-pip.py | python3.10 && \
    apt-get clean

RUN mkdir /ace-step-code && \
    git clone https://github.com/ace-step/ACE-Step.git /ace-step-code

RUN pip3.10 install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu121 && \
    pip3.10 install git+https://github.com/ace-step/ACE-Step.git --no-deps && \
    pip3.10 install fsspec jinja2 networkx sympy setuptools \
        diffusers transformers==4.50.0 accelerate peft soundfile \
        librosa loguru tqdm numpy click datasets==3.4.1 \
        pytorch_lightning==2.5.1 pypinyin num2words py3langid \
        hangul-romanize spacy thinc hf_transfer \
        runpod torchcodec typing_extensions \
        supabase && \
    pip3.10 install "click>=8.0"
    pip3.10 install supabase

RUN mkdir -p /app
COPY handler.py /app/handler.py

CMD ["python3.10", "/app/handler.py"]
