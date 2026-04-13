FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE.txt /app/
COPY edgar /app/edgar
COPY edgar_warehouse /app/edgar_warehouse

RUN pip install --upgrade pip \
    && python -c "import pathlib, tomllib; data = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); reqs = data['project']['optional-dependencies']['warehouse'] + data['project']['optional-dependencies']['s3']; pathlib.Path('/tmp/warehouse-requirements.txt').write_text('\n'.join(reqs) + '\n', encoding='utf-8')" \
    && pip install --no-compile --no-deps . \
    && pip install --no-compile -r /tmp/warehouse-requirements.txt \
    && rm /tmp/warehouse-requirements.txt

ENTRYPOINT ["edgar-warehouse"]
CMD ["--help"]
