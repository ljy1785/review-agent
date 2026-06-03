import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import run_agent

app = FastAPI(
    title="리뷰 분석 에이전트",
    description="상품 리뷰를 입력하면 속성별 감성 분석 결과를 반환합니다."
)

# ─── 요청/응답 모델 ───────────────────────────────────────
class ReviewInput(BaseModel):
    review: str
    max_retries: int = 2

class ReviewOutput(BaseModel):
    review: str
    items: list

# ─── 엔드포인트 ───────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze", response_model=ReviewOutput)
def analyze(input: ReviewInput):
    if not input.review.strip():
        raise HTTPException(status_code=400, detail="리뷰 내용을 입력해주세요.")

    result = run_agent(input.review, input.max_retries)
    return {
        "review": input.review,
        "items": result.get("items", [])
    }