from typing import List, Literal
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
import os

router = APIRouter()

def verify_s2s_key(x_ai_api_key: str = Header(None)):
    expected_key = os.getenv("X-AI-API-KEY") 
    if not expected_key or not x_ai_api_key or x_ai_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API Key")
    return x_ai_api_key

class UserActivity(BaseModel):
    user_id: int
    role: Literal["user", "admin"]
    account_age_days: int
    total_requests_created: int
    canceled_requests: int
    accepted_donations: int
    missed_donations: int
    reports_count: int

class MonitoringResponse(BaseModel):
    status: str
    user_id: int
    risk_score: int
    recommended_action: Literal["auto_ban", "flagged_for_review", "safe"]
    reasons: List[str]

def analyze_user_risk(data: UserActivity) -> tuple[int, Literal["auto_ban", "flagged_for_review", "safe"], List[str]]:
    if data.role == "admin":
        return 0, "safe", ["Admin - مستثنى من الفحص"]

    risk_score = 0
    reasons = []

    if data.accepted_donations > 2 and (data.missed_donations / data.accepted_donations) >= 0.40:
        risk_score += 50
        reasons.append(f"نسبة تخاذل عالية: وافق على {data.accepted_donations} ومراحش {data.missed_donations} مرات.")

    if data.total_requests_created > 3 and (data.canceled_requests / data.total_requests_created) >= 0.70:
        risk_score += 40
        reasons.append(f"معدل إلغاء مريب: أنشأ {data.total_requests_created} طلب ولغى {data.canceled_requests} منها.")

    if data.account_age_days < 7 and (data.total_requests_created > 5 or data.accepted_donations > 5):
        risk_score += 30
        reasons.append("نشاط مبالغ فيه لحساب جديد (عمره أقل من أسبوع).")

    if data.reports_count > 0:
        risk_score += (data.reports_count * 15)
        reasons.append(f"يوجد عدد {data.reports_count} بلاغات سابقة ضد هذا المستخدم.")

    risk_score = min(risk_score, 100)

    if risk_score >= 80:
        action = "auto_ban"
    elif risk_score >= 40:
        action = "flagged_for_review"
    else:
        action = "safe"

    return risk_score, action, reasons

@router.post("/monitor-user", response_model=MonitoringResponse)
async def monitor_user(data: UserActivity, api_key: str = Depends(verify_s2s_key)):
    try:
        risk_score, action, reasons = analyze_user_risk(data)
        return MonitoringResponse(
            status="success",
            user_id=data.user_id,
            risk_score=risk_score,
            recommended_action=action,
            reasons=reasons if reasons else ["الحساب آمن"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))