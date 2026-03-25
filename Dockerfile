FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir "websockets>=15.0" "openpyxl>=3.1"

COPY main.py .

EXPOSE 8080

CMD ["python", "-u", "main.py"]
