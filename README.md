# YTDownPC 1.1.0

Windows에서 YouTube·X·Instagram 영상, 사진, M4A 음원을 저장합니다. Android [YTDown](https://github.com/john3smith/ytdownForAND)의 다운로드·대기열·로그인 기능을 PC UI에 맞춰 추가했습니다.

- [GitHub Releases](https://github.com/john3smith/ytdownPC/releases): Windows portable ZIP
- [HTML 사용 설명서](docs/user-guide.html)
- [외부 구성요소 고지](THIRD_PARTY_NOTICES.md)

## 설치

버전별 portable ZIP 전체를 새 폴더에 풀고 `YTDownPC-v1.1.0.exe`를 실행하세요. EXE와 `_internal` 폴더를 함께 유지합니다. Qt 라이브러리를 교체 가능한 별도 파일로 제공하므로 EXE 하나만 옮겨서는 실행되지 않습니다. 이전 버전과 다운로드 파일을 지우지 않아도 됩니다.

처음 다운로드할 때 인터넷이 필요합니다. 최신 stable yt-dlp는 공식 GitHub Release에서 SHA-256 검증 후 준비합니다. 설치된 FFmpeg가 없으면 원본 imageio-ffmpeg 0.6.0 Windows wheel을 PyPI에서 SHA-256 검증 후 내려받아 사용자 PC에 준비합니다. 배포 ZIP에는 FFmpeg를 재포장하지 않습니다. 업데이트 확인 실패 시 검증된 기존 yt-dlp를 사용하며, FFmpeg 준비 실패는 오류로 표시합니다.

## Android판 기능의 PC 적용

| 기능 | PC 동작 |
|---|---|
| 영상·화질 | 최고 / 1080p 이하 / 720p 이하, 영상·음성 병합 |
| 음원만 추출 | M4A, 영상과 구분된 파일명, 사진만 있는 게시물은 음원 성공으로 처리하지 않음 |
| 사진·여러 장 사진 | X/Instagram 추출기를 확장해 사진 원본 저장, 이미지 형식 검증 |
| 공유/클립보드 | 링크 붙여넣기·텍스트 드롭과 바로 다운로드 ON/OFF |
| 대기열 | 한 번에 하나씩, 진행 항목 외 최대 10개 대기, 등록 시점 설정 유지 |
| 취소 | 선택 작업 취소, 전체 취소 1초 안에 두 번, 작업의 하위 프로세스까지 종료 |
| Wi-Fi에서만 시작 | Windows WLAN의 실제 연결 상태로 시작 대기, 시작한 작업은 연결 변경으로 중단하지 않음 |
| 사이트 로그인 | 앱 전용 HTTPS 웹뷰, YouTube/X/Instagram 별도 프로필, 세션 유지·선택 사이트 쿠키 삭제 |
| 현재 웹페이지 | HTTPS 페이지를 보고 뒤로/새로고침/닫기. 이 버튼은 다운로드를 시작하지 않음 |
| 계정 연속 다운로드 | X 프로필/게시물, Instagram 프로필/게시물 작성자 확인 → 검색 창 → 계정 검색 시작 → 계정 게시물 순차 저장 |
| 계정 검색 대기열 | 검색도 한 작업으로 예약, 뒤 작업 순서 유지, 개별 취소 |
| 끝 페이지 확인 | 타임라인/API의 종료 근거 확인, 시간/정체 제한에 걸린 부분 목록을 전체로 처리하지 않음 |
| 미완료 파일 | 앱 전용 `.ytdownpc-parts`의 `.part`, `.part-Frag숫자`, `.ytdl`만 조회·확인 삭제 |
| 진행률/진단 | 저장 속도·상태, 병합/변환 99%, 실제 파일 확인 후100%, 민감정보 제외 로그 복사 |
| 백그라운드 | 최소화·트레이에서 계속, 창 종료 시 유지/취소 선택 |
| HTTPS 연결 보조 | PC의 curl 기반 통신. Android 전용 TLS 릴레이와 구현은 다르며 인증서 검증 유지 |
| 라이브러리 업데이트 | 첫 작업 전 하루1회 stable 확인, 수동 확인, 체크섬 검증 및 다음 작업부터 적용 |

Android 공유 인텐트·MediaStore·포그라운드 알림·절전 서비스는 Windows에 그대로 이식하지 않고 붙여넣기/드롭·저장 폴더·트레이와 작업 목록으로 대응했습니다. 강제 종료 후 대기열 자동 복원은 Android판과 마찬가지로 제공하지 않습니다.

## 로그인과 계정 전체 미디어

1. 사이트 선택 → `로그인 / 웹페이지`에서 직접 로그인합니다. 기존 EGO/Chrome 로그인 저장소를 가져오지 않습니다.
2. X/Instagram 프로필 또는 게시물 주소를 입력하고 `계정 전체 미디어`를 누릅니다.
3. 열린 검색 창에서 로그인·접근 확인을 직접 완료하고 `계정 검색 시작`을 누릅니다.
4. 게시물 목록과 끝 페이지를 확인한 뒤 해당 계정의 다운로드를 순차 실행합니다. 일부 게시물이 실패하면 실패 수를 남기고 다음 게시물/대기 작업을 이어갑니다.

웹뷰에 쿠키가 존재한다는 표시는 로그인 성공 확인이 아닙니다. Google 등 일부 서비스는 임베디드 브라우저 로그인을 제한할 수 있습니다. 보안 확인·CAPTCHA·인증서 오류를 우회하지 않으며, 로그인/네트워크/사이트 구조 때문에 검색을 끝내지 못하면 명확히 실패로 표시합니다. 모든 계정의 전체 수집을 보장하지 않습니다.

## 저장·보안

- 기본 저장 위치는 Windows 사용자의 Downloads이며 설정에서 변경할 수 있습니다.
- 설정·앱 전용 브라우저 프로필·검증된 런타임은 `%LOCALAPPDATA%\YTDownPC`에 있습니다.
- 세션은 앱 브라우저 내부에서 사용합니다. 작업 프로세스로 전달하는 임시 데이터는 현재 Windows 사용자의 DPAPI로 암호화하고 작업 후 삭제합니다. 강제 종료 시 암호화된 임시 파일이 남을 수 있습니다.
- 쿠키/인증 헤더/서명 URL/비공개 경로를 진단 로그에 출력하지 않습니다. 검색·다운로드 목록은 실행 세션 메모리에 있습니다.
- 미완료 파일 삭제는 실행·대기·계정 검색 중 막고, 삭제 직전 경로·크기·수정 시각을 재확인합니다. 완료 파일/다른 폴더를 재귀 삭제하지 않습니다. GUI/MCP의 같은 출력 폴더 접근도 프로세스 잠금으로 보호합니다.
- DRM·유료·접근 권한 없는 게시물의 보호를 우회하지 않습니다. 본인이 소유하거나 저장을 허가받은 콘텐츠에 사용하세요.

## CLI / MCP

```powershell
.\.venv\Scripts\python.exe ytdownpc.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --probe
.\.venv\Scripts\python.exe ytdownpc.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --quality 720 --output "D:\Videos"
.\.venv\Scripts\python.exe ytdownpc.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --audio-only
```

로컬 stdio MCP는 `ytdownpc_mcp.py`입니다. 시작만으로 다운로드하지 않습니다.

- `video_info(url)` — 정보만 조회
- `start_download(url, quality="best", audio_only=false)` — 대기열 등록
- `download_status(job_id)` — 진행·완료·실제 파일 확인
- `cancel_download(job_id)` — 한 작업 취소

MCP는 브라우저 UI 없이 공개 자료 기준으로 동작합니다. GUI와 MCP의 대기열은 프로세스별이며 서버 종료 시 사라집니다. 기존 `start_download(url, quality)` 호출도 유지했습니다.

## 검증 범위

2026-10-21 개발 환경에서 공개 YouTube의 Blender Sintel 영상으로 720p MP4 병합과 M4A 음원 저장을 실제 완료했습니다. 사진은 합성 원본 바이트·이미지 형식 검증과 X/Instagram 추출기 fixture로 확인했습니다. 대기열 순서/설정 스냅샷/Wi-Fi 대기/계정 예약/부분 실패/취소 프로세스 트리/보수적 임시 파일 정리/URL 경계/DPAPI/MCP를 자동 검사합니다.

실제 X·Instagram 로그인 계정의 전체 수집, 모든 사이트의 최신 로그인 화면과 네트워크 조건은 미검증입니다. 지원 코드를 추가했다는 사실과 실제 계정 전체 다운로드 성공을 구분합니다. 릴리스 설명의 최종 빌드/패키지 검증 결과도 함께 확인하세요.

## 소스 실행 / 빌드

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ytdownpc.py
.\.venv\Scripts\python.exe -m unittest -q test_pc_features test_ytdownpc_mcp
.\.venv\Scripts\python.exe prepare_notices.py
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean YTDownPC.spec
```

빌드에는 Windows x64, Python3.12, Node.js가 필요합니다. spec은 프로젝트 상대 경로를 사용합니다. 결과는 `dist/YTDownPC-v1.1.0/`이며 폴더 전체를 배포합니다. Qt/PySide와 Node 등 외부 구성요소 버전·라이선스 고지를 보존해야 합니다. 비밀번호·브라우저 프로필·다운로드·로그·테스트 결과는 Git/배포에 포함하지 않습니다.
