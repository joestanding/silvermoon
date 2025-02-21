FROM python:3.8-slim

WORKDIR /app

COPY backend/ /app/
COPY --chown=root:root ../shared /app/shared

COPY backend/requirements.txt /app/
RUN pip install -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/shared:${PYTHONPATH}"

CMD ["python", "-u", "loop.py"]
