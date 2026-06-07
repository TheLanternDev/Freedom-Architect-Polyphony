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

# M-1: nie uruchamiaj jako root. Tworzymy dedykowanego usera bez powłoki i
# oddajemy mu /app (na wypadek gdyby runtime musiał zapisać np. dev-SQLite —
# w prod baza jest na Postgresie, więc app nie potrzebuje uprawnień zapisu do kodu).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && chown -R app:app /app
USER app

ENV PYTHONUNBUFFERED=1
# M-2: liczba workerów uvicorn sterowana env-em. Domyślnie 1 (zachowuje
# dotychczasowe zachowanie single-instance). Rate-limit i JTI/refresh działają
# globalnie przez Redis, więc >1 worker jest bezpieczny dla izolacji — pod
# warunkiem ustawienia REDIS_URL (wymagane w produkcji przez preflight).
ENV WEB_CONCURRENCY=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || exit 1
# Shell-form, żeby $WEB_CONCURRENCY uległ ekspansji (exec-form tego nie robi).
# `exec` zachowuje uvicorn jako PID 1 — poprawna obsługa sygnałów (SIGTERM → graceful).
CMD exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-1}"
