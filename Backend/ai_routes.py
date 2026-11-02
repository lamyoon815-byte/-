from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

if __package__:
    from .accounts import RateLimiter
    from .images import MAX_UPLOAD_BYTES, normalize_image
    from .recognition import image_quality
    from .catalog import Description
else:
    from accounts import RateLimiter
    from images import MAX_UPLOAD_BYTES, normalize_image
    from recognition import image_quality
    from catalog import Description


class RecognitionCandidate(BaseModel):
    artwork_id: str
    title: str
    artist: str
    score: float = Field(ge=-1, le=1, description="유사도 점수. 확률이나 정확도 백분율이 아닙니다.")
    image_url: str


class QualityResult(BaseModel):
    laplacian_variance: float
    highlight_ratio: float
    warnings: list[str]
    note: str


class RecognitionResult(BaseModel):
    mode: Literal["artwork", "placard"]
    candidates: list[RecognitionCandidate]
    score_type: Literal["cosine_similarity", "fuzzy_text_similarity"]
    status: Literal["needs_confirmation", "no_match"]
    quality: QualityResult


class AnalysisResult(BaseModel):
    description: Description
    review_status: Literal["unreviewed"]
    warning: str


class NarrationSegment(BaseModel):
    type: Literal["fact", "interpretation"]
    text: str


class NarrationResult(BaseModel):
    artwork_id: str
    mode: Literal["facts", "interpretations", "both"]
    segments: list[NarrationSegment]
    text: str
    review_status: Literal["reviewed"]


async def read_upload(image: UploadFile):
    try:
        if image.size is not None and image.size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "이미지는 10MB 이하여야 합니다.")
        content = await image.read(MAX_UPLOAD_BYTES + 1)
        if not content:
            raise HTTPException(400, "빈 파일입니다.")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "이미지는 10MB 이하여야 합니다.")
        return await run_in_threadpool(normalize_image, content)
    finally:
        await image.close()


def create_ai_router(catalog, accounts, current_user, recognition, gemini):
    router = APIRouter()
    ai_limiter = RateLimiter(attempts=5, window=60)

    @router.post("/recognize", response_model=RecognitionResult, tags=["작품 인식"], summary="촬영 사진·명패로 작품 후보 상위 3개 조회",
                 description="로그인 필요. mode=artwork는 CLIP 코사인 유사도, placard는 명패 텍스트 매칭 점수입니다. 점수는 확률이 아니며 후보 확인이 필요합니다. 사진은 저장하지 않습니다.")
    async def recognize(
        request: Request,
        user: Annotated[dict, Depends(current_user)],
        image: Annotated[UploadFile, File(description="작품 또는 명패 사진")],
        mode: Annotated[Literal["artwork", "placard"], Form()] = "artwork",
    ):
        normalized = await read_upload(image)
        quality = await run_in_threadpool(image_quality, normalized.content)
        if mode == "artwork":
            candidates = await run_in_threadpool(recognition.recognize_artwork, normalized.content)
            score_type = "cosine_similarity"
        else:
            ai_limiter.check(user["id"])
            extracted = await run_in_threadpool(gemini.read_placard, normalized.content)
            candidates = await run_in_threadpool(recognition.match_placard, extracted.title, extracted.artist, extracted.text)
            score_type = "fuzzy_text_similarity"
        for candidate in candidates:
            record = await run_in_threadpool(catalog.get, candidate["artwork_id"])
            candidate["image_url"] = str(request.url_for("artwork-images", path=record["image_filename"]))
        return {"mode": mode, "candidates": candidates, "score_type": score_type,
                "status": "needs_confirmation" if candidates else "no_match", "quality": quality}

    @router.post("/analyze", response_model=AnalysisResult, tags=["작품 해설"], summary="미등록 작품의 실시간 한국어 해설 생성",
                 description="로그인 필요. Gemini로 사실·감정 해석·영역·분위기 키워드를 생성합니다. 미검수 결과임을 표시하고 사진과 결과는 DB에 저장하지 않습니다.")
    async def analyze(user: Annotated[dict, Depends(current_user)], image: Annotated[UploadFile, File()]):
        ai_limiter.check(user["id"])
        normalized = await read_upload(image)
        description = await run_in_threadpool(gemini.describe, normalized.content)
        return {"description": description.model_dump(), "review_status": "unreviewed",
                "warning": "AI가 생성한 미검수 해설로 사실과 다른 내용이 포함될 수 있습니다."}

    @router.get("/artworks/{artwork_id}/narration", response_model=NarrationResult, tags=["작품 해설"], summary="내 감상 모드에 맞는 검수 해설 텍스트 조회",
                description="기본 모드는 계정의 narration_mode를 사용합니다. 반환된 text를 앱의 expo-speech로 재생합니다.")
    def narration(artwork_id: str, user: Annotated[dict, Depends(current_user)],
                  mode: Annotated[Literal["facts", "interpretations", "both"] | None, Query()] = None):
        record = catalog.get(artwork_id)
        if record is None:
            raise HTTPException(404, "등록된 작품을 찾을 수 없습니다.")
        if record["description"] is None:
            raise HTTPException(409, "검수된 해설이 아직 없습니다.")
        selected = mode or accounts.profile(user["id"]).narration_mode
        description = record["description"]
        segments = []
        if selected in {"facts", "both"}:
            segments.extend({"type": "fact", "text": text} for text in description["facts"])
        if selected in {"interpretations", "both"}:
            segments.extend({"type": "interpretation", "text": "가능한 감정적 해석입니다. " + text} for text in description["interpretations"])
        return {"artwork_id": artwork_id, "mode": selected, "segments": segments,
                "text": "\n".join(segment["text"] for segment in segments), "review_status": "reviewed"}

    return router
