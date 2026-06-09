FROM ghcr.io/ace-step/ace-step-1.5:0.1.8

RUN pip install runpod

COPY handler.py /app/handler.py

CMD ["python", "/app/handler.py"]
