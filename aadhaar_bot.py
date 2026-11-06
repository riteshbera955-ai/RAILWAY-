import os
import hashlib
import re
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from telegram import Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from PyPDF2 import PdfReader
import pytesseract
import logging

# CONFIG
TOKEN = "YOUR_BOT_TOKEN_FROM_BOTFATHER"
DATA_DIR = "/root/aadhaar_db/"
DUPE_LOG = DATA_DIR + "processed_hashes.txt"
TESS_DATA = "/usr/share/tesseract-ocr/4.00/tessdata/"  # Ensure 'hin' lang is installed

os.makedirs(DATA_DIR, exist_ok=True)
logging.basicConfig(level=logging.ERROR)

def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def is_duplicate(aadhaar_num):
    if not os.path.exists(DUPE_LOG):
        return False
    with open(DUPE_LOG, "r") as f:
        return aadhaar_num in f.read()

def log_processed(aadhaar_num):
    with open(DUPE_LOG, "a") as f:
        f.write(aadhaar_num + "\n")

def clean_text(text):
    return re.sub(r'\s+', '', text)

def extract_aadhaar_from_text(text):
    text = clean_text(text)
    match = re.search(r'(\d{4}\d{4}\d{4})', text)
    if match:
        return ''.join(match.group(1).split())
    return None

def extract_text_from_image(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    custom_config = '--oem 3 --psm 6 -l eng+hin'
    return pytesseract.image_to_string(thresh, config=custom_config)

def extract_aadhaar_from_pdf(pdf_path):
    # Try text extraction first
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    
    aadhaar = extract_aadhaar_from_text(text)
    if aadhaar:
        return aadhaar

    # Fallback: OCR on first page
    try:
        pages = convert_from_path(pdf_path, dpi=300, first_page=0, last_page=1)
        temp_img = "/tmp/ocr_page.jpg"
        pages[0].save(temp_img, "JPEG")

        # Preprocess for better OCR
        img_cv = cv2.imread(temp_img)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3,3), 0)
        _, adaptive = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cv2.imwrite(temp_img, adaptive)

        ocr_text = pytesseract.image_to_string(Image.open(temp_img), lang='eng+hin')
        os.remove(temp_img)
        return extract_aadhaar_from_text(ocr_text)
    except Exception as e:
        print(f"OCR failed: {e}")
        return None

def handle_pdf(update: Update, context: CallbackContext):
    message = update.message
    pdf_file = message.effective_attachment.get_file()
    original_filename = message.document.file_name
    temp_path = f"/tmp/{original_filename}"
    save_path = temp_path

    try:
        pdf_file.download(temp_path)
        
        # Check file hash to prevent dupe processing
        file_hash = get_file_hash(temp_path)
        if file_hash in open(DUPE_LOG).read():
            message.reply_text("❌ Duplicate file detected. Skipped.")
            os.remove(temp_path)
            return

        aadhaar = extract_aadhaar_from_pdf(temp_path)
        if not aadhaar:
            message.reply_text("❌ No Aadhaar number found.")
            os.rename(temp_path, f"{DATA_DIR}FAILED_{original_filename}")
            return

        # Remove spaces
        aadhaar = ''.join(aadhaar.split())
        if len(aadhaar) != 12 or not aadhaar.isdigit():
            message.reply_text(f"❌ Invalid Aadhaar format: {aadhaar}")
            return

        if is_duplicate(aadhaar):
            message.reply_text(f"🔁 Aadhaar {aadhaar} already processed. Skipping.")
            os.remove(temp_path)
            return

        # Rename and save
        new_path = f"{DATA_DIR}{aadhaar}.pdf"
        os.rename(temp_path, new_path)
        log_processed(aadhaar)
        
        message.reply_text(f"✅ Success! Saved as {aadhaar}.pdf")
        
    except Exception as e:
        message.reply_text(f"💥 Error: {str(e)}")
        if os.path.exists(temp_path):
            os.rename(temp_path, f"{DATA_DIR}ERROR_{original_filename}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.document.mime_type("application/pdf"), handle_pdf))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
