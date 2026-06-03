import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import run_agent
from database import init_db, insert_review, get_reviews

app = FastAPI(
    title="리뷰 분석 에이전트",
    description="상품 리뷰를 입력하면 속성별 감성 분석 결과를 반환합니다."
)

@app.on_event("startup")
def startup():
    init_db()

class ReviewInput(BaseModel):
    review: str
    max_retries: int = 2

class ReviewOutput(BaseModel):
    review: str
    items: list

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze", response_model=ReviewOutput)
def analyze(input: ReviewInput):
    if not input.review.strip():
        raise HTTPException(status_code=400, detail="리뷰 내용을 입력해주세요.")

    result = run_agent(input.review, input.max_retries)
    items = result.get("items", [])
    insert_review(input.review, items)

    return {"review": input.review, "items": items}

@app.get("/reviews")
def reviews():
    return get_reviews()