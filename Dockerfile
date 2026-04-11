FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip \
    && pip install ".[data,s3]"

ENTRYPOINT ["edgar-warehouse"]
CMD ["--help"]

