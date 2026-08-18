from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()

# Data Schemas
class UserActivity(BaseModel):
    user_id: int
    role: str
    account_age_days: int
    total_requests_created: int
    canceled_requests: int
    accepted_donations: int
    missed_donations: int  # وافق ومراحش
    reports_count: int

class MonitoringResponse(BaseModel):
    status: str
    user_id: int
    risk_score: int
    recommended_action: str  # "safe", "flagged_for_review", "auto_ban"
    reasons: List[str]

# Logic 
def analyze_user_risk(data: UserActivity):
    risk_score = 0
    reasons = []

    # تحليل المتخاذل للمتبرعين
    if data.accepted_donations > 2:
        miss_rate = data.missed_donations / data.accepted_donations
        if miss_rate >= 0.40:
            risk_score += 50
            reasons.append(f"نسبة تخاذل عالية: وافق على {data.accepted_donations} ومراحش {data.missed_donations} مرات.")
    
    # (Spam Requests)
    if data.total_requests_created > 3:
        cancel_rate = data.canceled_requests / data.total_requests_created
        if cancel_rate >= 0.70:
            risk_score += 40
            reasons.append(f"معدل إلغاء مريب: أنشأ {data.total_requests_created} طلب ولغى {data.canceled_requests} منها.")

    # (Fake Accounts)
    if data.account_age_days < 7:
        if data.total_requests_created > 5 or data.accepted_donations > 5:
            risk_score += 30
            reasons.append("نشاط مبالغ فيه لحساب جديد (عمره أقل من أسبوع).")

    # (Reports)
    if data.reports_count > 0:
        risk_score += (data.reports_count * 15)  # كل بلاغ بيزود الريسك 15 نقطة
        reasons.append(f"يوجد عدد {data.reports_count} بلاغات سابقة ضد هذا المستخدم")

    # تحديد القرار النهائي
    risk_score = min(risk_score, 100)
    
    if risk_score >= 80:
        action = "auto_ban"
    elif risk_score >= 40:
        action = "flagged_for_review"
    else:
        action = "safe"

    return risk_score, action, reasons
 
@router.post("/monitor-user", response_model=MonitoringResponse)
async def monitor_user(data: UserActivity):
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