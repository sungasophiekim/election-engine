"""
API Cache & Rate Limiter — API 호출 캐시 + 속도 제한
"필요할 때만, 캐시 우선, 간격 두고"

기능:
  1. TTL 기반 캐시 — 같은 데이터 중복 호출 방지
  2. API별 호출 간격 — rate limit 회피
  3. 호출 기록 — 마지막 호출 시각 + 성공/실패 추적
  4. 우선순위 — 쿼터 비싼 API는 아껴 씀
"""
from __future__ import annotations
import time
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class APICallRecord:
    """API 호출 기록"""
    api_name: str
    last_call: float = 0.0          # timestamp
    last_success: float = 0.0
    last_fail: float = 0.0
    call_count_today: int = 0
    fail_count_today: int = 0
    last_error: str = ""
    daily_limit: int = 0            # 0 = 무제한
    min_interval: float = 0.0       # 최소 호출 간격 (초)
    cache_ttl: float = 300.0        # 캐시 유지 시간 (초)

    def to_dict(self) -> dict:
        return {
            "api": self.api_name,
            "last_call": datetime.fromtimestamp(self.last_call).strftime("%H:%M:%S") if self.last_call > 0 else "—",
            "last_success": datetime.fromtimestamp(self.last_success).strftime("%H:%M:%S") if self.last_success > 0 else "—",
            "calls_today": self.call_count_today,
            "fails_today": self.fail_count_today,
            "daily_limit": self.daily_limit or "무제한",
            "remaining": (self.daily_limit - self.call_count_today) if self.daily_limit else "무제한",
            "cache_ttl": f"{self.cache_ttl:.0f}초",
            "last_error": self.last_error[:50] if self.last_error else "",
            "status": "ok" if not self.last_error else "error",
        }


# ═══════════════════════════════════════════════════════════════
# API별 설정
# ═══════════════════════════════════════════════════════════════

API_CONFIG = {
    "naver_news": APICallRecord(
        api_name="네이버 뉴스",
        daily_limit=25000,
        min_interval=0.3,       # 0.3초 간격
        cache_ttl=300,          # 5분 캐시
    ),
    "naver_datalab": APICallRecord(
        api_name="네이버 DataLab",
        daily_limit=1000,
        min_interval=1.0,       # 1초 간격
        cache_ttl=1800,         # 30분 캐시
    ),
    "youtube": APICallRecord(
        api_name="유튜브",
        daily_limit=10000,
        min_interval=1.0,
        cache_ttl=21600,        # 6시간 캐시 (쿼터 아낌)
    ),
    "google_trends": APICallRecord(
        api_name="구글 트렌드",
        daily_limit=0,          # 비공식
        min_interval=3.0,       # 3초 간격 (엄격)
        cache_ttl=1800,         # 30분
    ),
    "claude_ai": APICallRecord(
        api_name="Claude AI",
        daily_limit=0,
        min_interval=0.5,
        cache_ttl=3600,         # 1시간
    ),
    "community": APICallRecord(
        api_name="커뮤니티",
        daily_limit=25000,      # 네이버 웹검색 공유
        min_interval=0.5,
        cache_ttl=600,          # 10분
    ),
    "news_comment": APICallRecord(
        api_name="뉴스 댓글",
        daily_limit=0,
        min_interval=0.5,
        cache_ttl=600,
    ),
    "regional_media": APICallRecord(
        api_name="지역 언론",
        daily_limit=25000,
        min_interval=0.3,
        cache_ttl=600,
    ),
    "poll_auto": APICallRecord(
        api_name="여론조사 자동",
        daily_limit=25000,
        min_interval=0.3,
        cache_ttl=1800,         # 30분
    ),
}


# ═══════════════════════════════════════════════════════════════
# 캐시 저장소
# ═══════════════════════════════════════════════════════════════

_cache: dict[str, tuple[any, float]] = {}   # key → (data, timestamp)
_daily_reset: str = ""                       # 날짜 기반 리셋


def _check_daily_reset():
    """하루가 바뀌면 카운트 리셋."""
    global _daily_reset
    today = datetime.now().strftime("%Y-%m-%d")
    if today != _daily_reset:
        _daily_reset = today
        for rec in API_CONFIG.values():
            rec.call_count_today = 0
            rec.fail_count_today = 0
            rec.last_error = ""


def can_call(api_name: str) -> bool:
    """이 API를 지금 호출해도 되는지 확인."""
    _check_daily_reset()
    rec = API_CONFIG.get(api_name)
    if not rec:
        return True

    # 일일 한도 체크
    if rec.daily_limit > 0 and rec.call_count_today >= rec.daily_limit * 0.9:
        return False  # 90%에서 차단 (안전 마진)

    # 호출 간격 체크
    if rec.min_interval > 0 and time.time() - rec.last_call < rec.min_interval:
        return False

    return True


def get_cached(api_name: str, cache_key: str) -> any:
    """캐시에서 데이터 가져오기. 없거나 만료면 None."""
    full_key = f"{api_name}:{cache_key}"
    if full_key in _cache:
        data, ts = _cache[full_key]
        ttl = API_CONFIG.get(api_name, APICallRecord(api_name="")).cache_ttl
        if time.time() - ts < ttl:
            return data
    return None


def set_cached(api_name: str, cache_key: str, data: any):
    """캐시에 데이터 저장."""
    full_key = f"{api_name}:{cache_key}"
    _cache[full_key] = (data, time.time())


def record_call(api_name: str, success: bool = True, error: str = "", units: int = 1):
    """API 호출 기록."""
    _check_daily_reset()
    rec = API_CONFIG.get(api_name)
    if not rec:
        return
    rec.last_call = time.time()
    rec.call_count_today += units
    if success:
        rec.last_success = time.time()
        rec.last_error = ""
    else:
        rec.last_fail = time.time()
        rec.fail_count_today += 1
        rec.last_error = error


def wait_if_needed(api_name: str):
    """필요하면 대기 후 호출."""
    rec = API_CONFIG.get(api_name)
    if not rec:
        return
    elapsed = time.time() - rec.last_call
    if rec.min_interval > 0 and elapsed < rec.min_interval:
        time.sleep(rec.min_interval - elapsed)


def get_all_status() -> list[dict]:
    """모든 API 상태 반환 — 대시보드 표시용."""
    _check_daily_reset()
    return [rec.to_dict() for rec in API_CONFIG.values()]


def get_api_status(api_name: str) -> dict:
    """특정 API 상태."""
    rec = API_CONFIG.get(api_name)
    return rec.to_dict() if rec else {}
