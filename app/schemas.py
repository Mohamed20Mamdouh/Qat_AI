from pydantic import BaseModel
from typing import List, Optional

class FrontData(BaseModel):
    first_name: str
    second_name: str
    nid: str
    dob: str
    gender: str

class IDVerificationResponse(BaseModel):
    is_valid: bool
    message: List[str]
    front_data: Optional[FrontData] = None