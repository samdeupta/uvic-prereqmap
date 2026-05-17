FROM python:latest

WORKDIR /app

COPY backend/apis/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY backend/apis .
COPY backend/db db

EXPOSE 8000

CMD ["python", "start_all.py"]