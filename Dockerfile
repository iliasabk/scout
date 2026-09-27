FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scout/ ./scout/
COPY static/ ./static/
COPY run.py .

ENV SCOUT_PORT=8787
EXPOSE 8787
CMD ["python", "run.py", "serve"]
