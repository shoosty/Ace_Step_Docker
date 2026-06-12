FROM --platform=linux/amd64 runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# ACE-Step 1.5 XL — v50
# CUDA 12.4, PyTorch 2.4, pinned deps matching ACE-Step 1.5 requirements

RUN apt-get update && apt-get install -y git curl ffmpeg && apt-get clean

RUN mkdir /ace-step-code && \
    git clone https://github.com/ace-step/ACE-Step-1.5.git /ace-step-code

# Patch layer_type_validation import compatibility
RUN python3 -c "
import pathlib
p = pathlib.Path('/ace-step-code/acestep/models/common/configuration_acestep_v15.py')
txt = p.read_text()
txt = txt.replace(
    'from transformers.configuration_utils import PretrainedConfig, layer_type_validation',
    'from transformers.configuration_utils import PretrainedConfig\ntry:\n    from transformers.configuration_utils import layer_type_validation\nexcept ImportError:\n    def layer_type_validation(*args, **kwargs): pass'
)
p.write_text(txt)
print('Patched configuration_acestep_v15.py')
"

RUN pip install -e /ace-step-code --no-deps && \
    pip install fsspec jinja2 networkx sympy setuptools \
        "diffusers==0.31.0" "transformers>=4.51.0,<4.58.0" accelerate peft soundfile \
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
