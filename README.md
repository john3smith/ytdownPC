# YTDownPC — Windows 영상 다운로드 프로그램

YouTube, Instagram, X/Twitter의 **공개 영상 링크를 PC에 저장**하는 Windows 프로그램입니다. 그래픽 화면, 명령행, 로컬 MCP 인터페이스를 제공합니다. Android용 [ytdownForAND](https://github.com/john3smith/ytdownForAND)와는 별도 프로젝트입니다.

## 주요 기능

- 링크 붙여넣기, 저장 폴더 선택, 다운로드 진행률·속도 표시.
- 최고 화질 / 1080p 이하 / 720p 이하 선택.
- yt-dlp로 영상 다운로드, 포함된 FFmpeg로 영상·음성 병합.
- 명령행에서 영상 정보 조회 또는 다운로드.
- MCP의 `video_info`, `start_download`, `download_status`로 외부 도구에서 접근.

## 설치와 사용

현재 소스 버전은 **1.0.0**입니다. 이 저장소에는 아직 EXE Release가 없으며, 소스 실행 환경을 준비해야 합니다. 이미 Python 환경이 설치된 PC에서는 다음과 같이 실행할 수 있습니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ytdownpc.py
```

의존성 설치는 인터넷 연결이 필요합니다. `YTDownPC.cmd`는 준비된 `.venv`의 `pythonw.exe`로 화면을 엽니다. 영상 링크를 붙여넣고 화질과 저장 폴더를 선택한 후 다운로드를 누르세요. 기본 저장 위치는 **현재 Windows 사용자의 Downloads 폴더**입니다.

명령행 예시입니다. 아래 URL은 사용할 영상 주소로 바꾸세요.

```powershell
.\.venv\Scripts\python.exe ytdownpc.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --probe
.\.venv\Scripts\python.exe ytdownpc.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --quality 720 --output "D:\Videos"
```

## MCP 사용

MCP 클라이언트에 stdio 서버로 등록할 때 실행 파일은 프로젝트의 `.venv\Scripts\python.exe`, 인자는 `ytdownpc_mcp.py`의 절대 경로로 지정합니다. 서버 실행만으로 다운로드가 시작되지는 않습니다.

| 도구 | 하는 일 |
|---|---|
| `video_info(url)` | 다운로드 없이 제목·영상 정보 조회 |
| `start_download(url, quality="best")` | 비동기 다운로드 시작 후 작업 ID 반환 |
| `download_status(job_id)` | 진행률, 완료·실패 상태, 저장 파일 확인 |

화질 값은 `best`, `1080`, `720`입니다. MCP에서는 한 번에 한 작업만 실행하며, 상태는 서버 메모리에 저장됩니다. 다운로드 중 서버를 종료하면 작업 유지·자동 복원을 보장하지 않습니다. 다운로드 시작은 완료와 다르므로 상태와 출력 파일을 확인하세요.

## 제한과 주의사항

- 공개 영상 중심입니다. 사이트별 로그인, 계정 전체 수집, Android판의 음원 전용 토글은 이 PC판에 없습니다.
- DRM, 유료 콘텐츠, 접근 권한 없는 게시물은 지원하지 않습니다. 사이트 정책·구조 변경에 따라 일부 공개 링크도 실패할 수 있습니다.
- 저작권을 소유하거나 다운로드 허가를 받은 콘텐츠에만 사용하세요.
- 로그를 사용하면 URL·파일 경로 등이 포함될 수 있으니 공개 공유 전 검토하세요.

## 개발과 EXE 빌드

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_ytdownpc_mcp
```

`build-exe.cmd`는 PyInstaller를 실행합니다. 현재 `YTDownPC.spec`의 입력 경로는 원래 개발 환경의 `C:/ytdownpc/ytdownpc.py`로 설정되어 있으므로, 다른 PC에서는 **본인의 `ytdownpc.py` 경로로 수정**해야 합니다. 결과는 `dist/YTDownPC-v<버전>.exe`입니다. `.venv`, 다운로드 영상, 런타임 로그는 저장소에 포함되지 않습니다.
