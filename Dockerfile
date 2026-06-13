FROM python:3.11-slim

LABEL maintainer="AutoSign"
LABEL description="mhh1.com auto sign-in with Cloudflare bypass"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python3", "signin.py"]
