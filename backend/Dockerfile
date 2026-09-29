# Backend image: system ffmpeg is required for pydub/librosa + Opus decode.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Speaker-embedding model for the known-AI-voice check. Lives outside /app so
# the dev compose bind mount of ./backend doesn't hide it.
ARG SPEAKER_MODEL_URL=https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/nemo_en_titanet_small.onnx
ARG SPEAKER_MODEL_SHA256=ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e
RUN mkdir -p /opt/models \
    && curl -fsSL -o /opt/models/nemo_en_titanet_small.onnx "$SPEAKER_MODEL_URL" \
    && echo "$SPEAKER_MODEL_SHA256  /opt/models/nemo_en_titanet_small.onnx" | sha256sum -c -

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
