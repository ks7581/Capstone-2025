FROM python:3.11-slim

WORKDIR /controller

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .

CMD ["python", "controller.py"]
