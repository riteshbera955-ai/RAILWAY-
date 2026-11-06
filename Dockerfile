FROM python:3.9-slim

RUN apt update && apt install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Hindi OCR ইনস্টল
RUN mkdir -p /usr/share/tesseract-ocr/4.00/tessdata
RUN wget https://github.com/tesseract-ocr/tessdata/raw/main/hin.traineddata -O /usr/share/tesseract-ocr/4.00/tessdata/hin.traineddata

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir python-telegram-bot==13.30 PyPDF2 pdf2image Pillow opencv-python numpy pytesseract

ENV DATA_DIR=/app/data/

CMD ["python", "aadhaar_bot.py"]
