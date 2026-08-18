from app.schemas import IDVerificationResponse
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from datetime import datetime, date
from google import genai
from google.genai import types
from PIL import Image
import io
import json
import uuid
from pathlib import Path
import cv2
import numpy as np
import re
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
client = genai.Client()
router = APIRouter()

# Storage Setup
STORAGE_DIRS = {
    "front": Path("app/storage/id_cards"),
    "back": Path("app/storage/id_cards_back"),
    "faces": Path("app/storage/person_faces")
}

for path in STORAGE_DIRS.values():
    path.mkdir(parents=True, exist_ok=True)

# Helper Functions
def resize_image_if_needed(img_cv, max_width=1280):
    h, w = img_cv.shape[:2]
    if w > max_width:
        ratio = max_width / float(w)
        new_h = int(h * ratio)
        return cv2.resize(img_cv, (max_width, new_h), interpolation=cv2.INTER_AREA)
    return img_cv

def decode_national_id(nid: str):
    governorates = {
        '01': 'Cairo', '02': 'Alexandria', '03': 'Port Said', '04': 'Suez', 
        '11': 'Qalubia', '12': 'Dakahlia', '13': 'Ash Sharqia', '14': 'Gharbia', 
        '15': 'Menoufia', '16': 'Beheira', '17': 'Ismailia', '18': 'Giza', 
        '19': 'Beni Suef', '21': 'Fayoum', '22': 'El Menia', '23': 'Assiut', 
        '24': 'Sohag', '25': 'Qena', '26': 'Aswan', '27': 'Luxor', '28': 'Red Sea', 
        '29': 'New Valley', '31': 'Matrouh', '32': 'North Sinai', '33': 'South Sinai', '88': 'Outside Egypt'
    }
    try:
        century = "19" if nid[0] == '2' else "20"
        year = century + nid[1:3]
        month = nid[3:5]
        day = nid[5:7]
        dob = f"{day}-{month}-{year}"
        gov_code = nid[7:9]
        pob = governorates.get(gov_code, "Unknown")
        gender = "ذكر" if int(nid[12]) % 2 != 0 else "أنثى"
        return dob, pob, gender
    except Exception:
        return None, None, None

def extract_person_face(img_cv, save_path: Path):
    try:
        h_img, w_img, _ = img_cv.shape
        y1, y2 = int(h_img * 0.12), int(h_img * 0.62)
        x1, x2 = int(w_img * 0.08), int(w_img * 0.32)
        face_img = img_cv[y1:y2, x1:x2]
        return cv2.imwrite(str(save_path), face_img)
    except Exception:
        return False

def convert_arabic_numbers_to_english(text: str) -> str:
    if not text:
        return ""
    arabic_digits = "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹"
    english_digits = "01234567890123456789"
    translation_table = str.maketrans(arabic_digits, english_digits)
    return str(text).translate(translation_table)

def is_age_valid(dob_str: str) -> bool:
    try:
        dob = datetime.strptime(dob_str, "%d-%m-%Y").date()
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return 18 <= age <= 60
    except Exception:
        return False

def parse_gemini_json(response_text: str) -> dict:
    """Helper to cleanly extract JSON from Gemini's response"""
    clean_text = response_text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        raise ValueError("فشل في قراءة البيانات المستخرجة من البطاقة.")

# Main Endpoint
@router.post("/verify-full-id", response_model=IDVerificationResponse)
async def verify_full_id(
    front_id: UploadFile = File(...),
    back_id: UploadFile = File(...)
):
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if front_id.content_type not in allowed_types or back_id.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="عفوًا، الملفات المرفوعة يجب أن تكون صورًا (JPEG, PNG)."
        )

    try:
        front_contents = await front_id.read()
        back_contents = await back_id.read()

        file_id = str(uuid.uuid4())[:8]
        front_card_path = STORAGE_DIRS["front"] / f"card_front_{file_id}.jpg"
        back_card_path = STORAGE_DIRS["back"] / f"card_back_{file_id}.jpg"
        face_path = STORAGE_DIRS["faces"] / f"face_{file_id}.jpg"

        with open(front_card_path, "wb") as f: f.write(front_contents)
        with open(back_card_path, "wb") as f: f.write(back_contents)

        def process_images(front_bytes, back_bytes):
            front_cv = cv2.imdecode(np.frombuffer(front_bytes, np.uint8), cv2.IMREAD_COLOR)
            back_cv = cv2.imdecode(np.frombuffer(back_bytes, np.uint8), cv2.IMREAD_COLOR)

            extract_person_face(front_cv, face_path)

            front_optimized = resize_image_if_needed(front_cv, max_width=800)
            back_optimized = resize_image_if_needed(back_cv, max_width=800)

            _, encoded_front = cv2.imencode('.jpg', front_optimized, [cv2.IMWRITE_JPEG_QUALITY, 65])
            _, encoded_back = cv2.imencode('.jpg', back_optimized, [cv2.IMWRITE_JPEG_QUALITY, 65])
            return encoded_front.tobytes(), encoded_back.tobytes()

        # Run CPU-bound CV2 operations in a separate thread
        front_bytes_opt, back_bytes_opt = await asyncio.to_thread(
            process_images, front_contents, back_contents
        )

        front_pil = Image.open(io.BytesIO(front_bytes_opt))
        back_pil = Image.open(io.BytesIO(back_bytes_opt))

        combined_prompt = """أنت نظام OCR متقدم للبطاقات الشخصية المصرية. قم بتحليل صورتي وجه وظهر البطاقة المرفقتين معًا، واستخرج البيانات التالية بدقة شديدة في شكل كائن JSON نقي فقط بدون أي نصوص خارجية:
        {
            "front": {
                "first_name": "الاسم الأول",
                "second_name": "باقي الاسم",
                "address": "العنوان بالتفصيل",
                "nid": "الرقم القومي في أعلى الوجه (14 رقمًا)",
                "laser_number": "رقم المصنع الموجود أسفل الصورة ويبدأ بحرفين إنجليزي كابيتال و7 أرقام مثل GH1761219"
            },
            "back": {
                "back_nid": "الرقم القومي المكتوب في أعلى ظهر البطاقة (14 رقمًا)",
                "job": "المهنة",
                "religion": "الديانة",
                "marital_status": "الحالة الاجتماعية",
                "spouse_name": "اسم الزوج إن وُجد",
                "expiry_date": "تاريخ الانتهاء بالأرقام الإنجليزية"
            }
        }"""

        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[combined_prompt, front_pil, back_pil],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
                )
            )

        # Parse JSON cleanly
        data = parse_gemini_json(response.text)

        front_data = data.get("front", {})
        back_data = data.get("back", {})

        first_name = str(front_data.get("first_name", "")).strip()
        address = str(front_data.get("address", "")).strip()
        raw_nid = (front_data.get("nid") or front_data.get("national_id") or front_data.get("الرقم القومي") or "")
        clean_nid = re.sub(r'\D', '', str(raw_nid))
        dob, pob, gender = decode_national_id(clean_nid) if len(clean_nid) == 14 else (None, None, None)        
        age_valid = is_age_valid(dob) if dob else False
        laser_number = str(front_data.get("laser_number", "")).strip().upper()

        for key, value in back_data.items():
            if isinstance(value, str):
                back_data[key] = convert_arabic_numbers_to_english(value)

        back_nid_clean = re.sub(r'\D', '', str(back_data.get("back_nid", "")))
        
        rejection_reasons = []
        if not first_name or first_name in ["غير واضح", "مجهول", "None", "غير مقروء"]:
            rejection_reasons.append("اسم الشخص في وجه البطاقة غير واضح أو غير مقروء بوضوح.")
            
        if not address or address in ["غير واضح", "مجهول", "None", "غير مقروء"]:
            rejection_reasons.append("عنوان البطاقة غير واضح أو غير مقروء.")

        if len(clean_nid) != 14:
            rejection_reasons.append("الرقم القومي الأمامي غير صالح أو غير مكتمل.")

        if clean_nid != back_nid_clean:
            rejection_reasons.append("الرقم القومي في وجه البطاقة لا يتطابق مع الرقم القومي في ظهر البطاقة!")

        if not re.match(r'^[A-Z]{2}\d{7}$', laser_number):
            rejection_reasons.append(f"فشل التحقق: رقم المصنع غير صالح ({laser_number}).")

        if not age_valid:
            rejection_reasons.append("لا يمكن التسجيل كمتبرع. يجب أن يكون عمرك من 18 إلى 60 عامًا.")

        marital_status = str(back_data.get("marital_status", "")).strip()
        spouse_name = str(back_data.get("spouse_name", "")).strip()
        if "أعزب" in marital_status or "آنسة" in marital_status:
            if spouse_name and spouse_name not in ["لا يوجد", "none", "None", ""]:
                rejection_reasons.append("الحالة الاجتماعية 'أعزب/آنسة' ومع ذلك يوجد اسم زوج مسجل.")
        is_logically_valid = len(rejection_reasons) == 0
        if is_logically_valid:
            rejection_reasons = ["تم التحقق من صحة البطاقة ومطابقة البيانات بنجاح"]


        # Response payload
        response_payload = {
            "is_valid": is_logically_valid,
            "reasons": rejection_reasons,
            "storage_info": {
                "front_card_path": str(front_card_path),
                "back_card_path": str(back_card_path),
                "person_photo_path": str(face_path)
            },
            "front_data": {
                "first_name": first_name,
                "second_name": front_data.get("second_name", ""),
                "address": address,
                "nid": clean_nid,
                "laser_number": laser_number,
                "dob": dob,
                "gender": gender,
            } if is_logically_valid else None,
            "back_data": back_data if is_logically_valid else None
        }

        return response_payload

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"حدث خطأ داخلي: {str(e)}")