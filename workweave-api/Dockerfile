FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 120 --retries 5 -r requirements.txt
COPY workweave_api ./workweave_api
RUN useradd --uid 10001 --create-home workweave && mkdir -p /data/workweave && chown -R workweave:workweave /data
COPY docker-entrypoint.py /usr/local/bin/workweave-entrypoint.py
ENV WORKWEAVE_DATA_DIR=/data/workweave
EXPOSE 8000
ENTRYPOINT ["python", "/usr/local/bin/workweave-entrypoint.py"]
CMD ["uvicorn", "workweave_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
