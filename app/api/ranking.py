from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime

router = APIRouter()

class Candidate(BaseModel):
    user_id: int
    distance_km: float
    trust_score: float
    total_points: int
    days_since_last_donation: int
    response_rate_percent: float

class RankingRequest(BaseModel):
    request_id: int
    blood_group: str
    hospital_name: str
    created_at: str
    candidates: List[Candidate]

class RankedCandidate(BaseModel):
    user_id: int
    score: float
    priority_batch: int

class RankingResponse(BaseModel):
    status: str
    request_id: int
    ranked_candidates: List[RankedCandidate]
    recommended_notification_count: int

def calculate_candidate_score(candidate: Candidate, max_distance: float = 50.0) -> float:
    trust_score = (candidate.trust_score / 100) * 0.45
    resp_score = (candidate.response_rate_percent / 100) * 0.25
    dist = candidate.distance_km if candidate.distance_km < max_distance else max_distance
    dist_score = max(0, (max_distance - dist) / max_distance) * 0.25
    points_score = min(candidate.total_points / 1000, 1.0) * 0.5
    total_score = trust_score + resp_score + dist_score + points_score
    return round(max(min(total_score, 1.0), 0.0), 2)

@router.post("/rank-donors", response_model=RankingResponse)
async def rank_donors(data: RankingRequest):
    try:
        ranked_candidates = []
        for cand in data.candidates:
            if cand.days_since_last_donation < 90:
                continue
                
            score = calculate_candidate_score(cand)
            
            if score >= 0.80:
                batch = 1
            elif score >= 0.60:
                batch = 2
            elif score >= 0.40:
                batch = 3
            else:
                batch = 4
                
            ranked_candidates.append(
                RankedCandidate(
                    user_id=cand.user_id,
                    score=score,
                    priority_batch=batch
                )
            )
            
        ranked_candidates.sort(key=lambda x: x.score, reverse=True)
        try:
            req_time = datetime.strptime(data.created_at, "%Y-%m-%d %H:%M:%S")
            request_hour = req_time.hour
            
            if 23 <= request_hour < 7:
                base_count = 15
            else:
                base_count = 5
                
        except ValueError:
            base_count = 5
            
        recommended_count = min(base_count, len(ranked_candidates))
        
        return RankingResponse(
            status="success",
            request_id=data.request_id,
            ranked_candidates=ranked_candidates,
            recommended_notification_count=recommended_count,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
