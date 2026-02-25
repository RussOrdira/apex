FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apex_predict ./apex_predict
COPY infra ./infra

RUN pip install --upgrade pip \
    && pip install .[dev]

EXPOSE 8000
