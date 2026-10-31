"""Android-compatible link handling, stream progress and actionable diagnostics."""
from __future__ import annotations

import math
import re
from urllib.parse import parse_qsl, urlsplit


def stream_video_url(value):
    """Return a canonical supported video link, never a profile/login page."""
    p = urlsplit(value)
    host = (p.hostname or '').lower()
    if host != 'pornhub.com' and not host.endswith('.pornhub.com'):
        return None
    video_id = None
    if re.fullmatch(r'/embed/[a-z0-9]{1,128}/?', p.path):
        video_id = p.path.strip('/').split('/')[1]
    elif p.path in {'/view_video.php', '/video/show'}:
        ids = [v for k, v in parse_qsl(p.query, keep_blank_values=True) if k == 'viewkey']
        if len(ids) == 1 and re.fullmatch(r'[a-z0-9]{1,128}', ids[0]):
            video_id = ids[0]
    if not video_id:
        raise ValueError('동영상 주소의 viewkey 또는 embed ID를 확인해 주세요.')
    return 'https://www.pornhub.com/view_video.php?viewkey=' + video_id


def extract_media_url(text):
    from pc_engine import validate_media_url
    for candidate in re.findall(r'https?://[^\s<>"\u201c\u201d]+', text or ''):
        try:
            return validate_media_url(candidate.rstrip('.,!?)\u3002\u3001'))
        except ValueError:
            continue
    return None


def failure_advice(message):
    error = str(message).lower()
    groups = [
        (('certificate verify failed', 'certificate_verify_failed', 'ssl certificate problem'),
         '서버 인증서 확인 실패: PC 날짜·시간과 네트워크를 확인해 주세요.'),
        (('no impersonate target', 'curl_cffi is not installed'),
         '브라우저 통신 모듈을 불러오지 못했습니다. 최신 PC 배포 폴더 전체를 확인해 주세요.'),
        (('connection reset', 'reset by peer', 'winerror 10054', 'remote end closed'),
         '사이트 또는 네트워크가 연결을 종료했습니다. 일반 브라우저에서 같은 링크가 열리는지 확인해 주세요.'),
        (('http error 403', 'http error 401', '403 forbidden', '401 unauthorized', 'server returned 403', 'server returned 401'),
         '접근이 거절됐습니다. 앱 로그인·현재 웹페이지에서 접근 상태를 직접 확인해 주세요.'),
        (('http error 404', '404 not found', 'server returned 404'),
         '링크를 찾을 수 없습니다. 삭제 또는 주소 변경 여부를 확인해 주세요.'),
        (('timed out', 'timeout'), '서버 응답 시간이 초과됐습니다. 인터넷 연결과 페이지 접속 상태를 확인해 주세요.'),
        (('ffmpeg exited', 'ffmpeg exited with code'),
         'FFmpeg가 저장 중 종료됐습니다. 종료 코드만으로 원인을 확정할 수 없습니다.'),
    ]
    return next((advice for terms, advice in groups if any(t in error for t in terms)), None)


class StreamProgress:
    """FFmpeg -progress protocol; 100% belongs to verified completion only."""
    def __init__(self, duration=None, is_live=False):
        self.duration = (float(duration) if type(duration) in (int, float)
                         and math.isfinite(duration) and 0 < duration <= 31536000 and not is_live else 0)
        self.elapsed = 0
        self.size = 0

    def accept(self, line):
        key, _, value = line.strip().partition('=')
        if key in {'out_time_us', 'out_time_ms', 'total_size'}:
            if re.fullmatch(r'\d{1,18}', value):
                if key == 'total_size':
                    self.size = max(self.size, int(value))
                else:
                    self.elapsed = max(self.elapsed, int(value) / 1000000)
        elif key == 'progress' and value in {'continue', 'end'}:
            return dict(stage='streaming', percent=min(99, int(self.elapsed / self.duration * 100)) if self.duration else None,
                        elapsed=self.elapsed, duration=self.duration, downloaded=self.size)
