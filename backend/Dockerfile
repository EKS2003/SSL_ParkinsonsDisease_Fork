FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /app/data

RUN pip install opencv-python-headless

RUN pip install mediapipe

RUN pip install fastAPI

RUN pip install uvicorn

RUN pip install python-multipart

RUN pip install sqlalchemy

COPY . .

ENV port = 8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--reload"]