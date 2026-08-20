from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List
from datetime import datetime
import os

router = APIRouter()

def verify_s2s_key(x_ai_api_key: str = Header(None)):
    expected_key = os.getenv("X_AI_API_KEY") 
    if not expected_key or not x_ai_api_key or x_ai_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API Key")
    return x_ai_api_key

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
    expansion_step: int 

def calculate_candidate_score(candidate: Candidate, max_distance: float = 50.0) -> float:
    trust_score = (candidate.trust_score / 100) * 0.45
    resp_score = (candidate.response_rate_percent / 100) * 0.25
    dist = candidate.distance_km if candidate.distance_km < max_distance else max_distance
    dist_score = max(0, (max_distance - dist) / max_distance) * 0.25
    points_score = min(candidate.total_points / 1000, 1.0) * 0.5
    
    total_score = trust_score + resp_score + dist_score + points_score
    return round(max(min(total_score, 1.0), 0.0), 2)

def get_recommended_count(created_at: str, candidates_count: int) -> int:
    try:
        req_time = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        base_count = 15 if 23 <= req_time.hour or req_time.hour < 7 else 5
    except ValueError:
        base_count = 5
        
    return min(base_count, candidates_count)

@router.post("/rank-donors", response_model=RankingResponse)
async def rank_donors(data: RankingRequest, api_key: str = Depends(verify_s2s_key)):
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
        recommended_count = get_recommended_count(data.created_at, len(ranked_candidates))
        
        return RankingResponse(
            status="success",
            request_id=data.request_id,
            ranked_candidates=ranked_candidates,
            recommended_notification_count=recommended_count,
            expansion_step=5
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))