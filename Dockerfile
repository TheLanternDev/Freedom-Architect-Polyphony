FROM python:3.13-slim-bookworm
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents ./agents
COPY api ./api
COPY config ./config
COPY core ./core
COPY db ./db
COPY business_fa2 ./business_fa2
COPY modes ./modes
COPY env_bootstrap.py .
COPY main.py .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
