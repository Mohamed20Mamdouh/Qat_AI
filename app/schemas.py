from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class FrontData(BaseModel):
    first_name: str
    second_name: str
    nid: str
    dob: str
    gender: str

class IDVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    is_valid: bool
    message: Optional[str] = None
    reasons: Optional[List[str]] = None
    front_data: Optional[FrontData] = None