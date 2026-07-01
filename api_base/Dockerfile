FROM python:3.10-slim

WORKDIR /app

# OCR dependencies
RUN apt-get update \
	&& apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "run_api.py"]