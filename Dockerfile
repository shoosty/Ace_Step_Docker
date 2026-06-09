FROM runpod/base:0.6.2-cuda12.1.0

RUN apt-get update && apt-get install -y python3.10 git curl && \
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
        hangul-romanize spacy thinc torchvision hf_transfer \
        runpod torchcodec typing_extensions && \
    pip3.10 install "click>=8.0"

RUN mkdir -p /app
COPY handler.py /app/handler.py

CMD ["python3.10", "/app/handler.py"]
