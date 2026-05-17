FROM python:latest

WORKDIR /app

COPY backend/scrapers/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY backend/scrapers .
COPY backend/db db

CMD ["python", "-u", "run_all.py"]