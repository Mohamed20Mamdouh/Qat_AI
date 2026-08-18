from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import verification
from app.api import ranking
from app.api import monitoring

app = FastAPI(title="Qatrah AI Engine", description="AI Qatrah P2P Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(verification.router, prefix="/api/v1", tags=["ID Verification"])
app.include_router(ranking.router, prefix="/api/v1", tags=["Smart Ranking"])
app.include_router(monitoring.router, prefix="/api/v1", tags=["Fraud & Abuse Monitoring"])

@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "Welcome to Qatrah AI Engine. Server is running Successfully!"
    }

