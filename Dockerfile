FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements/runtime.txt /app/requirements/runtime.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements/runtime.txt

COPY chatbot /app/chatbot
COPY workflows /app/workflows
COPY scripts/cfcbot /app/scripts/cfcbot
COPY Dockerfile compose.yaml compose.test.yaml /app/

WORKDIR /app/chatbot/server
EXPOSE 7777

CMD ["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "7777"]
