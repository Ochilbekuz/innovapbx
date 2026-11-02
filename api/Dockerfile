# Innova PBX — API qatlami (FastAPI, Python 3.12).
FROM python:3.12-slim

# M4b: `pg_dump -Fc`/`pg_restore` MIJOZI serverning o'zi (postgres:16) bilan BIR XIL
# katta versiyada bo'lishi SHART — bookworm'ning o'z repo'sidagi `postgresql-client`
# 15'ga tushadi (16 bilan mos emas), shu sabab PGDG rasmiy repo'sidan `-client-16` olinadi.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg gnupg lsb-release \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
       https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
       https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y gnupg lsb-release \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/api

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY entrypoint.sh /usr/local/bin/innova-api-entrypoint.sh
RUN chmod +x /usr/local/bin/innova-api-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/innova-api-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
