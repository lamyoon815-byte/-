# SWAITHON Backend

Python 3.12 기반 FastAPI 서버. 명령은 Backend 폴더에서 실행한다.

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install --python .venv/bin/python -r requirements.txt
./.venv/bin/python -m uvicorn main:app --reload
```

- `/health`: 서버 상태 확인
- `/upload`: multipart `image` 검증·회전 보정·RGB JPEG 변환, 영구 저장 없음
- `/docs`: 한국어 API 문서

업로드는 JPEG·PNG·WebP·HEIC/HEIF, 최대 10MiB·2,500만 화소를 지원한다.
