YTDownPC
========

현재 버전
  1.0.0

실행
  YTDownPC.cmd 파일을 더블클릭합니다.

EXE 빌드
  build-exe.cmd 파일을 실행합니다.
  version_info.py의 APP_VERSION을 올리면 GUI 제목과 EXE 파일명에 함께 반영됩니다.
  결과 파일: dist\YTDownPC-v<버전>.exe

저장 위치
  기본 폴더: Windows 다운로드 폴더
  현재 경로: C:\Users\123\Downloads

지원 범위
  공개 YouTube, Instagram, X/Twitter 영상과 종료된 공개 YouTube 라이브를 다운로드합니다.
  DRM, 유료, 비공개 또는 별도 로그인이 필요한 영상은 지원하지 않습니다.

자동 실행
  혤캉 라이브 종료 감시기가 종료를 확인하면 아래 주소를 자동 다운로드합니다.
  https://www.youtube.com/watch?v=j459OKBvgAw

구성
  ytdownpc.py          : GUI 및 명령행 프로그램
  .venv                 : 전용 Python 환경
  auto-download.log     : 자동 다운로드 로그

Codex MCP
  ytdownpc_mcp.py      : 로컬 stdio MCP 서버 (Codex CLI에 ytdownpc 이름으로 등록)
  video_info(url)      : 다운로드 없이 공개 영상 정보 조회
  start_download(url, quality="best") : Windows 다운로드 폴더로 비동기 저장
  download_status(job_id) : 진행 상태 및 저장 파일 확인
  MCP를 켜는 것만으로 다운로드는 시작되지 않습니다.
  다운로드 작업 상태는 MCP 서버 메모리에 보관되므로 서버 재시작 시 사라집니다.
  테스트: .venv\Scripts\python.exe -m unittest -q test_ytdownpc_mcp
