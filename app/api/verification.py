from app.schemas import IDVerificationResponse
from fastapi import APIRouter, UploadFile, File, status, Header, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, date
from google import genai
from google.genai import types
from PIL import Image
import io
import json
import cv2
import numpy as np
import re
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()
router = APIRouter()

def verify_s2s_key(x_ai_api_key: str = Header(None)):
    expected_key = os.getenv("X-AI-API-KEY") 
    if not expected_key or not x_ai_api_key or x_ai_api_key != expected_key:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized: Invalid or missing API Key"})
    return x_ai_api_key

def resize_image_if_needed(img_cv, max_width=1280):
    h, w = img_cv.shape[:2]
    if w > max_width:
        new_h = int(h * (max_width / float(w)))
        return cv2.resize(img_cv, (max_width, new_h), interpolation=cv2.INTER_AREA)
    return img_cv

def decode_national_id(nid: str):
    if len(nid) != 14:
        return None, None
    try:
        century = "19" if nid[0] == '2' else "20"
        year, month, day = century + nid[1:3], nid[3:5], nid[5:7]
        gender = "ذكر" if int(nid[12]) % 2 != 0 else "أنثى"
        return f"{day}-{month}-{year}", gender
    except Exception:
        return None, None

def convert_arabic_numbers_to_english(text: str) -> str:
    return str(text).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")) if text else ""

def is_age_valid(dob_str: str) -> bool:
    try:
        dob = datetime.strptime(dob_str, "%d-%m-%Y").date()
        today = date.today()
        return 18 <= (today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))) <= 60
    except Exception:
        return False

@router.post("/verify-full-id", response_model=IDVerificationResponse)
async def verify_full_id(
    front_id: UploadFile = File(...), 
    back_id: UploadFile = File(...),
    api_key: str = Depends(verify_s2s_key)
):
    if isinstance(api_key, JSONResponse):
        return api_key

    allowed_types = {"image/jpeg", "image/png", "image/jpg"}
    if front_id.content_type not in allowed_types or back_id.content_type not in allowed_types:
        return JSONResponse(status_code=400, content={"detail": "عفوًا، الملفات المرفوعة يجب أن تكون صورًا (JPEG, PNG)."})

    try:
        front_contents, back_contents = await asyncio.gather(front_id.read(), back_id.read())
        
        def process_images(front_bytes, back_bytes):
            front_cv = cv2.imdecode(np.frombuffer(front_bytes, np.uint8), cv2.IMREAD_COLOR)
            back_cv = cv2.imdecode(np.frombuffer(back_bytes, np.uint8), cv2.IMREAD_COLOR)
            
            _, encoded_front = cv2.imencode('.jpg', resize_image_if_needed(front_cv, 800), [cv2.IMWRITE_JPEG_QUALITY, 65])
            _, encoded_back = cv2.imencode('.jpg', resize_image_if_needed(back_cv, 800), [cv2.IMWRITE_JPEG_QUALITY, 65])
            
            return encoded_front.tobytes(), encoded_back.tobytes()

        front_bytes_opt, back_bytes_opt = await asyncio.to_thread(process_images, front_contents, back_contents)
        
        combined_prompt = """أنت نظام OCR متقدم. استخرج البيانات التالية بدقة في شكل JSON نقي:
        {
            "front": {
                "first_name": "الاسم الأول",
                "second_name": "باقي الاسم",
                "address": "العنوان بالتفصيل",
                "nid": "الرقم القومي (14 رقمًا)",
                "laser_number": "رقم المصنع أسفل الصورة"
            },
            "back": {
                "back_nid": "الرقم القومي بظهر البطاقة",
                "marital_status": "الحالة الاجتماعية",
                "spouse_name": "اسم الزوج إن وُجد"
            }
        }"""

        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[combined_prompt, Image.open(io.BytesIO(front_bytes_opt)), Image.open(io.BytesIO(back_bytes_opt))],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )

        data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
        front_data, back_data = data.get("front", {}), data.get("back", {})

        first_name = str(front_data.get("first_name", "")).strip()
        address = str(front_data.get("address", "")).strip()
        clean_nid = re.sub(r'\D', '', str(front_data.get("nid", "")))
        laser_number = str(front_data.get("laser_number", "")).strip().upper()
        
        dob, gender = decode_national_id(clean_nid)
        back_nid_clean = convert_arabic_numbers_to_english(re.sub(r'\D', '', str(back_data.get("back_nid", ""))))

        rejection_reasons = []
        if not first_name or first_name in ["غير واضح", "مجهول", "None", "غير مقروء"]:
            rejection_reasons.append("اسم الشخص في وجه البطاقة غير واضح أو غير مقروء بوضوح.")
        if not address or address in ["غير واضح", "مجهول", "None", "غير مقروء"]:
            rejection_reasons.append("عنوان البطاقة غير واضح أو غير مقروء.")
        if len(clean_nid) != 14:
            rejection_reasons.append("الرقم القومي الأمامي غير صالح أو غير مكتمل.")
        elif clean_nid != back_nid_clean:
            rejection_reasons.append("الرقم القومي في وجه البطاقة لا يتطابق مع الرقم القومي في ظهر البطاقة!")
        if not re.match(r'^[A-Z]{2}\d{7}$', laser_number):
            rejection_reasons.append(f"فشل التحقق: رقم المصنع غير صالح ({laser_number}).")
        if not is_age_valid(dob) if dob else True:
            rejection_reasons.append("لا يمكن التسجيل كمتبرع. يجب أن يكون عمرك من 18 إلى 60 عامًا.")

        marital_status = str(back_data.get("marital_status", "")).strip()
        spouse_name = str(back_data.get("spouse_name", "")).strip()
        if any(word in marital_status for word in ["أعزب", "آنسة"]) and spouse_name not in ["لا يوجد", "none", "None", ""]:
            rejection_reasons.append("الحالة الاجتماعية 'أعزب/آنسة' ومع ذلك يوجد اسم زوج مسجل.")

        is_logically_valid = len(rejection_reasons) == 0

        if is_logically_valid:
            return JSONResponse(
                status_code=200,
                content={
                    "is_valid": True,
                    "message": "تم التحقق من صحة البطاقة ومطابقة البيانات بنجاح",
                    "front_data": {
                        "first_name": first_name,
                        "second_name": front_data.get("second_name", ""),
                        "nid": clean_nid,
                        "dob": dob,
                        "gender": gender,
                    }
                }
            )
        else:
            return JSONResponse(
                status_code=422,
                content={
                    "is_valid": False,
                    "reasons": rejection_reasons,
                    "front_data": None
                }
            )

    except json.JSONDecodeError:
        return JSONResponse(status_code=422, content={"detail": "فشل في قراءة البيانات المستخرجة من البطاقة."})
    except ValueError as ve:
        return JSONResponse(status_code=422, content={"detail": str(ve)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"حدث خطأ داخلي: {str(e)}"})