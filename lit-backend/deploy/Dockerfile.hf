FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PATH=/home/user/.local/bin:$PATH

# FAISS needs the OpenMP runtime. Keep the base image small by omitting build tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 user \
    && mkdir -p /home/user/app \
    && chown user:user /home/user/app

USER user
WORKDIR /home/user/app

# Dependency changes invalidate this layer; application edits do not.
COPY --chown=user:user requirements.txt ./
# Install PyTorch's CPU wheel first. It satisfies the torch==2.9.1 pin below
# without pulling the much larger CUDA dependencies from PyPI.
RUN pip install --user --index-url https://download.pytorch.org/whl/cpu \
        'torch==2.9.1+cpu' \
    && pip install --user -r requirements.txt \
    && python -c "import torch, faiss, sklearn, joblib; assert torch.version.cuda is None"

# Cache the public fallback embedder in the image so restarts do not download it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY --chown=user:user . ./
RUN mkdir -p logs fixtures data "$HF_HOME"

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=3))['status'] == 'healthy'"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
