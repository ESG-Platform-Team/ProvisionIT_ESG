# The API as one container image. Used by Cloudflare Containers (see
# cloudflare/ and DEPLOY.md) and runs the same anywhere Docker does.
#
#   docker build -t provisionit-esg-api backend
#   docker run -p 8080:8080 --env-file backend/.env provisionit-esg-api

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY fixture-site ./fixture-site
COPY start.sh .
RUN chmod +x start.sh && useradd --create-home esg && mkdir data && chown esg data
USER esg

EXPOSE 8080
CMD ["./start.sh"]
