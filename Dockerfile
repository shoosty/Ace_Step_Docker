FROM ghcr.io/ace-step/ace-step-1.5:0.1.8

RUN uv pip install runpod --system

COPY handler.py /app/handler.py

CMD ["python", "/app/handler.py"]
