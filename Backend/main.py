from fastapi import FastAPI

if __package__:
    from .images import upload_image
else:
    from images import upload_image


def create_app():
    application = FastAPI(title="SWAITHON API")

    @application.get("/health", summary="서버 상태 확인", tags=["서버 상태"])
    def health_check():
        return {"status": "ok"}

    application.add_api_route("/upload", upload_image, methods=["POST"],
        summary="사진 업로드 및 JPEG 변환", tags=["사진 업로드"])
    return application


app = create_app()
