from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi import Path as PathParameter
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

if __package__:
    from .catalog import ArtworkDetail, ArtworkList, CatalogStore
    from .images import normalize_image, upload_image
else:
    from catalog import ArtworkDetail, ArtworkList, CatalogStore
    from images import normalize_image, upload_image



def health_check():
    return {"status": "ok"}


def create_app(data_dir: Path | None = None) -> FastAPI:
    store = CatalogStore(data_dir)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        await run_in_threadpool(store.initialize)
        yield

    application = FastAPI(
        title="SWAITHON API",
        description=(
            "작품 사진 업로드와 등록 작품 조회를 제공하는 백엔드 API입니다.\n\n"
            "작품 조회 결과의 `image_url`을 열면 등록된 원본 이미지를 볼 수 있습니다. "
            "원본 이미지는 `/images/{filename}`에서 제공됩니다."
        ),
        openapi_tags=[
            {"name": "서버 상태", "description": "서버가 정상적으로 응답하는지 확인합니다."},
            {"name": "사진 업로드", "description": "사용자 촬영 사진의 검증과 전처리를 확인합니다."},
            {"name": "작품 조회", "description": "SQLite에 등록된 작품 정보·해설·원본 이미지 URL을 조회합니다."},
        ],
        lifespan=lifespan,
    )
    application.state.catalog = store
    origins = [item.strip() for item in os.environ.get("CORS_ORIGINS", "http://localhost:8081,http://127.0.0.1:8081").split(",") if item.strip()]
    if origins:
        application.add_middleware(CORSMiddleware, allow_origins=origins,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

    @application.middleware("http")
    async def private_cache_control(request: Request, call_next):
        response = await call_next(request)
        if request.headers.get("authorization") or request.url.path.startswith(("/me", "/auth", "/analyze", "/recognize")):
            response.headers["Cache-Control"] = "no-store"
        return response

    application.add_api_route(
        "/health", health_check, methods=["GET"], tags=["서버 상태"],
        summary="서버 상태 확인",
        description="서버가 정상적으로 실행 중이면 `status: ok`를 반환합니다.",
    )
    application.add_api_route(
        "/upload", upload_image, methods=["POST"], tags=["사진 업로드"],
        summary="사진 업로드 및 JPEG 변환",
        description=(
            "사진의 실제 형식을 검사하고 회전 보정·RGB 변환 후 JPEG로 인코딩합니다. "
            "응답의 `source_format`은 입력 형식, `format`은 변환된 형식입니다. "
            "현재는 변환 결과의 크기·가로·세로 등 정보만 반환하며, "
            "사진을 영구 저장하거나 작품 DB에 등록하지 않습니다."
        ),
        responses={
            400: {"description": "빈 파일이거나 읽을 수 없는 이미지"},
            413: {"description": "파일 용량 또는 이미지 해상도 제한 초과"},
            415: {"description": "지원하지 않는 이미지 형식"},
        },
    )
    application.mount(
        "/images",
        StaticFiles(directory=store.images_dir, check_dir=False),
        name="artwork-images",
    )

    def public_artwork(record: dict, request: Request) -> dict:
        filename = record.pop("image_filename")
        record["image_url"] = str(request.url_for("artwork-images", path=filename))
        return record

    @application.get(
        "/artworks", response_model=ArtworkList, tags=["작품 조회"],
        summary="등록된 작품 목록 조회",
        description=(
            "DB에 등록된 작품 목록과 전체 작품 수를 반환합니다. "
            "`limit`과 `offset`으로 조회 범위를 지정할 수 있습니다. "
            "각 작품에는 원본 이미지 URL이 포함되며, 미검수 해설은 `null`로 반환합니다."
        ),
    )
    def list_artworks(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=100, description="한 번에 가져올 작품 수 (1~100)")] = 20,
        offset: Annotated[int, Query(ge=0, description="앞에서 건너뛸 작품 수 (0부터 시작)")] = 0,
    ):
        records, total = store.list(limit, offset)
        return {
            "items": [public_artwork(record, request) for record in records],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @application.get(
        "/artworks/{artwork_id}", response_model=ArtworkDetail, tags=["작품 조회"],
        summary="작품 상세 정보 조회",
        description=(
            "작품 ID로 제목·작가·제작 시기·배경·출처·이용 조건과 원본 이미지 URL을 조회합니다. "
            "사람이 검수한 해설이 있으면 함께 반환하며, 미검수 상태이면 해설은 `null`입니다. "
            "예시 작품 ID는 `mona-lisa`입니다."
        ),
        responses={404: {"description": "해당 ID로 등록된 작품이 없음"}},
    )
    def get_artwork(
        artwork_id: Annotated[str, PathParameter(description="조회할 작품의 고유 ID", examples=["mona-lisa"])],
        request: Request,
    ):
        record = store.get(artwork_id)
        if record is None:
            raise HTTPException(status_code=404, detail="등록된 작품을 찾을 수 없습니다.")
        return public_artwork(record, request)

    return application


app = create_app()
