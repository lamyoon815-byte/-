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

## 작품 카탈로그

`python import_catalog.py catalog.demo.json`으로 포함된 모나리자 데모를 등록한다.
`GET /artworks`는 목록, `GET /artworks/{id}`는 작품 정보와 원본 이미지 URL을 반환한다.
DB와 이미지 복사본은 `data/`에 저장하며 미검수 해설은 노출하지 않는다.

## 회원 인증·개인 설정

`/auth/register`, `/auth/login`으로 발급된 토큰을 Bearer 인증에 사용한다.
`/auth/logout`은 세션을 폐기한다. 세션은 7일 후 만료된다.
`/me/profile`에서 계정별 설정을 조회·전체 저장하고 `/me/history`에서 개인 관람 기록을 관리한다.
비밀번호는 Argon2, DB의 세션 토큰은 SHA-256 해시로 저장한다.
회원 데이터는 `data/users.sqlite3`에 저장한다.
