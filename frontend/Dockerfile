FROM python:3.8-slim

WORKDIR /app

COPY frontend/ /app/
COPY --chown=root:root ../shared /app/shared

COPY frontend/requirements.txt /app/
RUN pip install -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app:/app/shared:${PYTHONPATH}"

CMD ["python", "-u", "run.py"]

