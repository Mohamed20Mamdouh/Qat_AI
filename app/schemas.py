from pydantic import BaseModel
from typing import Optional, Dict, Any

class FrontOCRData(BaseModel):
    first_name: Optional[str] = ""
    second_name: Optional[str] = ""
    address: Optional[str] = ""
    nid: Optional[str] = ""
    dob: Optional[str] = ""
    gender: Optional[str] = ""

class BackOCRData(BaseModel):
    job: Optional[str] = ""
    religion: Optional[str] = ""
    marital_status: Optional[str] = ""
    spouse_name: Optional[str] = ""
    serial_number: Optional[str] = ""
    expiry_date: Optional[str] = ""

class StorageInfo(BaseModel):
    front_card_path: str
    back_card_path: str
    person_photo_path: Optional[str] = None

class IDVerificationResponse(BaseModel):
    is_valid: bool
    message: str
    storage_info: Optional[StorageInfo] = None
    front_data: Optional[FrontOCRData] = None
    back_data: Optional[BackOCRData] = None