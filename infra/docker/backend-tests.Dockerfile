FROM python:latest

WORKDIR /app

COPY backend/apis/requirements.txt apis-requirements.txt
COPY backend/scrapers/requirements.txt scrapers-requirements.txt
RUN pip install --no-cache-dir -r apis-requirements.txt -r scrapers-requirements.txt pytest

COPY backend .

CMD ["pytest"]