# Qatrah AI Engine

An advanced artificial intelligence and computer vision backend engine developed by the Qatrah team as part of a university graduation project. Built using FastAPI, Google Gemini API, and OpenCV, this engine automates the verification of Egyptian National ID cards (Front and Back), performs precise OCR data extraction, crops user face photos, decodes National ID numbers mathematically, and enforces strict security and fraud-prevention checks.

---

## Key Features

* **Combined Single-Call AI Processing:** Analyzes both front and back ID card images simultaneously in a single optimized Gemini API call to maximize processing speed and conserve API rate limits (Quota).

* **Advanced OCR Data Extraction:** Extracts front-card data (first name, full/second name, detailed address, 14-digit national ID, and the Laser Number / رقم المصنع) and back-card data (back-card national ID, job, religion, marital status, spouse name, card expiry date, and issuing code) with strict prompt constraints.

* **Strict Security & Fraud Prevention (Cross-Validation):**

1. Compares the front 14-digit National ID with the back-card top National ID to guarantee both images belong to the exact same document.

2. Validates the strict format of the Laser Number (^[A-Z]{2}\d{7}$) as a mandatory acceptance criteria.

3. Performs logical checks (e.g., matching marital status with spouse name availability).

4. Mathematical National ID Decoding: Instantly decodes the 14-digit National ID to extract Date of Birth (DOB), Gender, and Place of Birth (Governorate) with a 0% error rate.

5. Computer Vision (OpenCV): Automatically detects, crops, and saves the citizen's face photo, while optimizing and resizing card images before cloud processing.

6. Strict Pydantic & Sanitization Validation: Structured response models, automatic Arabic-to-English number normalization, and auto-documentation via Swagger UI.
---

## Tech Stack

* **Python 3.10+**

* **FastAPI (High-performance web framework)**

* **Google GenAI SDK (gemini-2.5-flash model - Async API)**

* **OpenCV & NumPy (Image processing and face extraction)**

* **Pydantic (Data validation and schema management)**

* **Pillow & python-dotenv (Image handling and environment configuration)**

---

## Project Directory Structure

```text
qatrah_ai_engine/
│
├── app/
│   ├── api/
│   │   └── verification.py    # Main API router, AI processing, and security validation logic
│   ├── storage/               # Local storage for cards and extracted faces
│   │   ├── id_cards/
│   │   ├── id_cards_back/
│   │   └── person_faces/
│   ├── main.py                # FastAPI application entry point
│   └── schemas.py             # Pydantic data models
│
├── .env                       # Environment variables (API Key)
├── requirements.txt           # Project Python dependencies
└── README.md                  # Project documentation
```
---

## Installation & Local Setup

1. Clone or Open Project Directory:
```Bach
cd qatrah_ai_engine
```
2. Create and Activate a Virtual Environment:
```Bash
python -m venv venv
#On Windows:
venv\Scripts\activate
#on Mac or Linux:
. venv/bin/activate
```
3. Install Dependencies:
Ensure your requirements.txt is up to date, then run:

```Bash
pip install -r requirements.txt
```
4. Configure Environment Variables:
Create a .env file in the root directory and add your Google Gemini API key:

```Bach
GEMINI_API_KEY=your_google_gemini_api_key_here
```
5. Run the Server:
```Bach
Bashuvicorn app.main:app --reload
```
* The server will start locally at: http://127.0.0.1:8000

* You can access the interactive Swagger documentation at: http://127.0.0.1:8000/docs

## API Documentation & Contract

Verify Full ID Endpoint
* Route: /api/v1/verify-full-id
* Method: POST
* Content-Type: multipart/form-data

## Request Parameters (Form-Data)
ــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ
| Field Name  |     Type     |              Description                                        |
| front_image | File (Image) | Front side of the Egyptian National ID card (.jpg, .png, .webp) |
| back_image  | File (Image) | Back side of the Egyptian National ID card (.jpg, .png, .webp)  |
ــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ
## Successful Response Format (200 OK)
```JSON
{
  "is_valid": true,
  "message": "تم التحقق من صحة البطاقة ومطابقة البيانات بنجاح",
  "storage_info": {
    "front_card_path": "app/storage/id_cards/card_front_xxxx.jpg",
    "back_card_path": "app/storage/id_cards_back/card_back_xxxx.jpg",
    "person_photo_path": "app/storage/person_faces/face_xxxx.jpg"
  },
  "front_ocr_data": {
    "first_name": "أحمد",
    "second_name": "عبدالحميد السيد...",
    "address": "١٣ ش المترأس - غرب النوبارية مينا البصل - الاسكندرية",
    "nid": "29710200200311",
    "laser_number": "JE0085978",
    "dob": "20-10-1997",
    "gender": "ذكر",
    "pob": "Alexandria"
  },
  "back_ocr_data": {
    "back_nid": "29710200200311",
    "job": "طالب",
    "religion": "مسلم",
    "marital_status": "أعزب",
    "spouse_name": "",
    "expiry_date": "2029/03/08",
    "issuing_code": "11"
  }
}
```
## Error / Rejection Responses (is_valid: false)
**Returned with status 200 OK or validation codes if security/logical checks fail (e.g., NID mismatch between front and back, invalid laser number format, or mismatched marital status):**

```Json
{
  "is_valid": false,
  "message": "خطأ أمني: الرقم القومي في وجه البطاقة لا يتطابق مع الرقم القومي في ظهر البطاقة!",
  "storage_info": {
    "front_card_path": "app/storage/id_cards/card_front_xxxx.jpg",
    "back_card_path": "app/storage/id_cards_back/card_back_xxxx.jpg",
    "person_photo_path": "app/storage/person_faces/face_xxxx.jpg"
  },
  "front_ocr_data": null,
  "back_ocr_data": null
}
```
* **400 Bad Request:** Returned if uploaded files are missing, invalid image formats, or exceed limits.


* **500 Internal Server Error:** Returned if an unexpected server-side error or API quota limit (429) occurs.

## Requirements
**requirements.txt**

fastapi
uvicorn[standard]
python-multipart
pydantic
google-genai
opencv-python
numpy
Pillow
python-dotenv
pandas
scikit-learn
httpx