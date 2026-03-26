"""
중앙선거여론조사심의위원회 (nesdc.go.kr) 자동 스크래퍼
경남 광역단체장선거 여론조사 수집 → PDF 파싱 → DB 저장
"""
from __future__ import annotations

import io
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://nesdc.go.kr"
LIST_URL = f"{BASE_URL}/portal/bbs/B0000005/list.do?menuNo=200467"
VIEW_URL = f"{BASE_URL}/portal/bbs/B0000005/view.do"
FILE_URL = f"{BASE_URL}/portal/cmm/fms/FileDown.do"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# 우리 후보 / 상대 후보 (config에서 가져올 수 있으나 기본값 설정)
DEFAULT_CANDIDATE = "김경수"
DEFAULT_OPPONENT = "박완수"


@dataclass
class NesdcPoll:
    """nesdc.go.kr에서 수집한 여론조사 1건"""
    ntt_id: str
    reg_no: str = ""
    org: str = ""                     # 조사기관명
    client: str = ""                  # 조사의뢰자
    survey_date: str = ""             # 조사 시작일 (YYYY-MM-DD)
    pub_date: str = ""                # 공표일 (YYYY-MM-DD)
    sample_size: int = 0
    margin_of_error: float = 3.0
    method: str = ""                  # 조사방법
    our_support: float = 0.0          # 우리 후보 지지율
    opponent_support: dict = field(default_factory=dict)  # {이름: 지지율}
    undecided: float = 0.0
    source_url: str = ""
    pdf_parsed: bool = False


class NesdcScraper:
    """중앙선거여론조사심의위원회 경남 광역단체장 여론조사 수집기"""

    def __init__(self, candidate: str = DEFAULT_CANDIDATE,
                 opponent: str = DEFAULT_OPPONENT,
                 max_pages: int = 80):
        self.candidate = candidate
        self.opponent = opponent
        self.max_pages = max_pages

    # ──────────────────────────────────────────────
    # 1. 목록 스캔 — 경남 광역단체장선거 nttId 수집
    # ──────────────────────────────────────────────
    def scan_list(self) -> list[dict]:
        """경남 광역단체장선거 여론조사 목록 반환 [{nttId, text, reg_date}, ...]"""
        results = []
        for page in range(1, self.max_pages + 1):
            data = urllib.parse.urlencode({"pageIndex": str(page)}).encode("utf-8")
            req = urllib.request.Request(LIST_URL, data=data)
            req.add_header("User-Agent", UA)
            try:
                resp = urllib.request.urlopen(req, timeout=15)
                html = resp.read().decode("utf-8")
            except Exception as e:
                logger.warning(f"Page {page} fetch failed: {e}")
                break

            ntt_ids = list(set(re.findall(r"nttId=(\d+)", html)))
            if not ntt_ids:
                break

            items = re.findall(r'<a[^>]*nttId=(\d+)[^>]*>(.*?)</a>', html, re.DOTALL)
            for nid, content in items:
                text = re.sub(r"<[^>]+>", " ", content).strip()
                text = re.sub(r"\s+", " ", text)
                if "경상남도" in text and "광역단체장" in text:
                    # 등록일 추출
                    date_m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                    results.append({
                        "ntt_id": nid,
                        "text": text,
                        "reg_date": date_m.group(1) if date_m else "",
                    })

        logger.info(f"Found {len(results)} 경남 광역단체장 polls")
        return results

    # ──────────────────────────────────────────────
    # 2. 상세 페이지 파싱 — 메타데이터 추출
    # ──────────────────────────────────────────────
    def fetch_detail(self, ntt_id: str) -> NesdcPoll:
        """상세 페이지에서 조사기관/표본/오차/공표일 등 메타 추출"""
        url = f"{VIEW_URL}?nttId={ntt_id}&menuNo=200467"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8")

        poll = NesdcPoll(ntt_id=ntt_id, source_url=url)

        # th-td 쌍 추출
        fields: dict[str, str] = {}
        rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
        for row in rows:
            ths = re.findall(r"<th[^>]*>(.*?)</th>", row, re.DOTALL)
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            for th, td in zip(ths, tds):
                th_c = re.sub(r"<[^>]+>", "", th).strip()
                td_c = re.sub(r"<[^>]+>", " ", td).strip()
                td_c = re.sub(r"\s+", " ", td_c).replace("&nbsp;", " ").replace("&plusmn;", "±")
                if th_c and th_c not in fields:
                    fields[th_c] = td_c

        poll.org = fields.get("조사기관명", "")
        poll.client = fields.get("조사의뢰자", "")
        poll.method = fields.get("조사방법1", "")

        # 등록번호
        reg_no = fields.get("등록 글번호", "")
        poll.reg_no = re.sub(r"\D", "", reg_no)

        # 조사일
        date_raw = fields.get("조사일시", "")
        date_m = re.search(r"(\d{4}-\d{2}-\d{2})", date_raw)
        poll.survey_date = date_m.group(1) if date_m else ""

        # 공표일
        pub_raw = fields.get("최초 공표·보도 지정일시", "")
        pub_m = re.search(r"(\d{4}-\d{2}-\d{2})", pub_raw)
        poll.pub_date = pub_m.group(1) if pub_m else ""

        # 표본수
        sample_raw = fields.get("접촉 후 응답완료 사례수 (I) 합계", "0")
        sample_digits = re.sub(r"\D", "", sample_raw)
        poll.sample_size = int(sample_digits) if sample_digits else 0

        # 오차 — "95% 신뢰수준에 ±3.1%P"
        moe_raw = fields.get("표본오차", "")
        moe_m = re.search(r"±\s*(\d+\.?\d*)%", moe_raw)
        poll.margin_of_error = float(moe_m.group(1)) if moe_m else 3.0

        # PDF 다운로드 파라미터 추출
        poll._html = html  # 임시 보관 (PDF 다운로드용)

        return poll

    # ──────────────────────────────────────────────
    # 3. PDF 다운로드 + 지지율 파싱
    # ──────────────────────────────────────────────
    def parse_poll_pdf(self, poll: NesdcPoll) -> bool:
        """결과분석/통계표 PDF에서 후보 지지율 추출"""
        html = getattr(poll, "_html", "")
        if not html:
            return False

        # view() 호출 파라미터 추출: view('atchFileId', 'fileSn', 'bbsId', 'bbsKey')
        pdf_params = re.findall(
            r"view\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'\)",
            html,
        )
        if not pdf_params:
            logger.info(f"nttId={poll.ntt_id}: PDF 미공개 (공표 후 24h 미경과)")
            return False

        # 파일 이름 추출
        pdf_names = re.findall(r">\s*([^<]*\.pdf)\s*</a>", html, re.IGNORECASE)

        # 통계표/결과표 PDF 우선 시도, 실패하면 다른 PDF도 시도
        priority = []
        for i, name in enumerate(pdf_names):
            if "통계" in name or "결과" in name:
                priority.insert(0, i)
            else:
                priority.append(i)
        # 이름 매칭 안 되면 전체 인덱스
        if not priority:
            priority = list(range(len(pdf_params)))

        for idx in priority:
            if idx >= len(pdf_params):
                continue

            atch_id, file_sn, bbs_id, bbs_key = pdf_params[idx]
            download_url = (
                f"{FILE_URL}?atchFileId={atch_id}&fileSn={file_sn}"
                f"&bbsId={bbs_id}&bbsKey={bbs_key}"
            )

            try:
                req = urllib.request.Request(download_url)
                req.add_header("User-Agent", UA)
                resp = urllib.request.urlopen(req, timeout=30)
                pdf_data = resp.read()
            except Exception as e:
                logger.warning(f"PDF download failed (idx={idx}): {e}")
                continue

            if pdf_data[:5] != b"%PDF-":
                continue

            if self._extract_support_from_pdf(pdf_data, poll):
                return True

        return False

    def _extract_support_from_pdf(self, pdf_data: bytes, poll: NesdcPoll) -> bool:
        """PDF 텍스트에서 김경수 vs 박완수 양자대결 지지율 추출

        여론조사 PDF는 기관마다 포맷이 다르므로 여러 전략으로 시도:
        1) 양자대결 페이지에서 "전체" 행 바로 뒤 숫자 (한국갤럽 등)
        2) 양자대결 섹션 내 "전체" 행 뒤 소수점 포함 숫자 (리얼미터 등)
        3) 전체 텍스트에서 정규식 패턴 매칭 (fallback)
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF not installed: pip install pymupdf")
            return False

        doc = fitz.open(stream=pdf_data, filetype="pdf")
        candidate = self.candidate
        opponent = self.opponent

        # ── 전략 1+2: 양자대결 페이지에서 "전체" 행 추출 ──
        for page_num in range(doc.page_count):
            text = doc[page_num].get_text()

            # 양자대결 + 우리 후보 + 상대 후보 모두 포함된 페이지만
            has_matchup = ("양자" in text and "대결" in text) or "양자대결" in text
            has_matchup = has_matchup or ("도지사" in text and "가상" in text)
            if not has_matchup:
                continue
            if candidate not in text and opponent not in text:
                continue

            lines = text.split("\n")

            # 양자대결+김경수+박완수 헤더 위치 탐색 (±5줄 이내에 두 후보 이름)
            matchup_start = -1
            for i, line in enumerate(lines):
                if candidate not in line:
                    continue
                # 상대 후보가 같은 줄 또는 ±5줄 이내
                nearby = range(max(0, i - 5), min(len(lines), i + 6))
                has_opponent = any(opponent in lines[j] for j in nearby)
                if not has_opponent:
                    continue
                # "양자" 또는 "대결"이 위 10줄 이내에 있는지
                context = "".join(lines[max(0, i - 10):i + 1])
                if "양자" in context or "대결" in context or "가상" in context:
                    matchup_start = i
                    break

            # matchup_start 못 찾으면 이 페이지 건너뛰기
            # (정당지지도 등 다른 섹션의 "전체" 행을 잘못 매칭하는 것 방지)
            if matchup_start < 0:
                continue

            # matchup_start 이후 ~ 다음 섹션 시작 전까지만 탐색
            search_end = len(lines)
            for i in range(matchup_start + 3, len(lines)):
                line_lower = lines[i].strip()
                # 다른 양자대결 또는 정당지지도 섹션 시작이면 중단
                if ("양자" in line_lower and "대결" in line_lower and
                        candidate not in line_lower and opponent not in line_lower):
                    search_end = i
                    break
                if "정당지지도" in line_lower or "정당 지지도" in line_lower:
                    search_end = i
                    break

            # matchup_start ~ 전체 사이에서 후보 컬럼 순서 감지
            # 한 줄에 한 이름만 있는 컬럼 헤더를 기준으로 판단
            # (서던포스트: 박완수 먼저, 리얼미터: 김경수 먼저)
            candidate_first = True  # 기본: 우리 후보가 첫 번째 컬럼
            cand_pos = opp_pos = -1
            for i in range(matchup_start, min(matchup_start + 25, search_end)):
                line_text = lines[i]
                has_cand = candidate in line_text
                has_opp = opponent in line_text
                # 양쪽 모두 있는 줄(타이틀)은 건너뛰기
                if has_cand and has_opp:
                    continue
                if has_cand and cand_pos < 0:
                    cand_pos = i
                if has_opp and opp_pos < 0:
                    opp_pos = i
            if cand_pos > 0 and opp_pos > 0 and opp_pos < cand_pos:
                candidate_first = False

            for i in range(matchup_start, search_end):
                stripped = lines[i].strip()
                is_total = ("전체" in stripped or "전 체" in stripped) and "하위" not in stripped
                if not is_total:
                    continue

                # "전체" 행 바로 위에 "정당" 관련 키워드가 있으면 건너뛰기
                above = "".join(lines[max(0, i - 8):i])
                if "정당지지도" in above and "양자" not in above:
                    continue

                # "전체" 다음에 나오는 숫자들 수집 (최대 12줄)
                numbers: list[float] = []
                for j in range(i, min(i + 12, len(lines))):
                    nums = re.findall(r"(\d+\.?\d+|\d+)", lines[j])
                    for n in nums:
                        val = float(n)
                        # 사례수(큰 숫자)는 건너뛰기
                        if val > 100:
                            continue
                        numbers.append(val)

                result = self._match_support_pattern(
                    numbers, poll, candidate, opponent,
                    candidate_first=candidate_first,
                )
                if result:
                    doc.close()
                    return True

        # ── 전략 2.5: 양자대결 키워드 없이 후보 컬럼 + "전체" 행이 있는 페이지 ──
        # KSOI 등 "가상대결" 키워드가 별도 페이지에 있고 데이터 테이블에는 없는 경우
        for page_num in range(doc.page_count):
            text = doc[page_num].get_text()
            if candidate not in text or opponent not in text:
                continue
            lines = text.split("\n")

            # 컬럼 헤더에 두 후보가 있고 (±5줄 이내), "전체" 행이 있는지
            cand_line = opp_line = total_line = -1
            for i, line in enumerate(lines[:30]):
                if candidate in line and opponent not in line and cand_line < 0:
                    cand_line = i
                if opponent in line and candidate not in line and opp_line < 0:
                    opp_line = i
                if ("전체" in line or "전 체" in line) and "하위" not in line and total_line < 0:
                    total_line = i

            if cand_line < 0 or opp_line < 0 or total_line < 0:
                continue
            if abs(cand_line - opp_line) > 8:
                continue
            # 두 후보만 있는 페이지여야 함 (다자대결 제외)
            # "계" 또는 100.0이 전체 행 근처에 있는지 확인
            candidate_first = cand_line < opp_line

            # 숫자 추출
            numbers: list[float] = []
            for j in range(total_line, min(total_line + 12, len(lines))):
                nums = re.findall(r"(\d+\.?\d+|\d+)", lines[j])
                for n in nums:
                    val = float(n)
                    if val > 100:
                        continue
                    numbers.append(val)

            # 다자대결 페이지인지 확인 (후보 3명 이상이면 건너뛰기)
            other_candidates = ["김두관", "김태호", "민홍철", "조해진"]
            other_count = sum(1 for oc in other_candidates
                             if any(oc in lines[i] for i in range(min(20, len(lines)))))
            if other_count >= 2:
                continue

            result = self._match_support_pattern(
                numbers, poll, candidate, opponent,
                candidate_first=candidate_first,
            )
            if result:
                doc.close()
                return True

        # ── 전략 3: 전체 텍스트에서 패턴 매칭 (fallback) ──
        full_text = "\n".join(doc[p].get_text() for p in range(doc.page_count))
        doc.close()

        # "전체/전 체" + (N)(N) + 숫자들
        patterns = [
            # 한국갤럽 스타일: 전      체 ■ ■ (1,008) (1,008) 43 45 6 7 100
            r"전\s*체.*?■.*?■.*?\(\d[\d,]*\)\s*\(\d[\d,]*\)\s*"
            r"(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+100",
            # 리얼미터 스타일: 전체 (1001) (1001) 41.1 43.3 4.0 6.1 5.4
            r"전체\s*\(\d+\)\s*\(\d+\)\s*"
            r"(\d+\.?\d+)\s+(\d+\.?\d+)\s+(\d+\.?\d+)\s+(\d+\.?\d+)\s+(\d+\.?\d+)",
            # KBS 스타일: 전 체 (805) (805) 30  29  3  3  1
            r"전\s+체\s*\(\d[\d,]*\)\s*\(\d[\d,]*\)\s*"
            r"(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)",
            # 서던포스트 스타일: ◈ 전 체 ◈ (1,007) 28.5 28.3 ...
            r"[◈]?\s*전\s*체\s*[◈]?\s*\(\d[\d,]*\)\s*"
            r"(\d+\.?\d+)\s+(\d+\.?\d+)\s+(\d+\.?\d+)\s+(\d+\.?\d+)",
        ]

        for pat in patterns:
            for m in re.finditer(pat, full_text, re.DOTALL):
                vals = [float(m.group(g)) for g in range(1, m.lastindex + 1)]
                our_val, opp_val = vals[0], vals[1]
                if 10 <= our_val <= 80 and 10 <= opp_val <= 80:
                    poll.our_support = our_val
                    poll.opponent_support = {opponent: opp_val}
                    poll.undecided = sum(vals[2:]) if len(vals) > 2 else 0
                    poll.pdf_parsed = True
                    logger.info(
                        f"nttId={poll.ntt_id} (regex): {candidate} {our_val}% vs "
                        f"{opponent} {opp_val}%"
                    )
                    return True

        logger.warning(f"nttId={poll.ntt_id}: 지지율 추출 실패")
        return False

    def _match_support_pattern(
        self, numbers: list[float], poll: NesdcPoll,
        candidate: str, opponent: str,
        candidate_first: bool = True,
    ) -> bool:
        """숫자 리스트에서 양자대결 지지율 패턴 매칭

        candidate_first: True면 첫 번째 숫자가 우리 후보, False면 상대 후보가 먼저.
        예상 패턴:
        - [43, 45, 6, 7, 100] → (한국갤럽: 정수, 합계 100)
        - [41.1, 43.3, 4.0, 6.1, 5.4] → (리얼미터: 소수)
        """
        if len(numbers) < 3:
            return False

        def _assign(first_val: float, second_val: float, undecided: float):
            """candidate_first에 따라 올바른 후보에 값 할당"""
            if candidate_first:
                poll.our_support = first_val
                poll.opponent_support = {opponent: second_val}
            else:
                poll.our_support = second_val
                poll.opponent_support = {opponent: first_val}
            poll.undecided = undecided
            poll.pdf_parsed = True

        # 100으로 끝나는 패턴 (한국갤럽 스타일)
        for j in range(len(numbers)):
            if numbers[j] == 100 and j >= 4:
                first_val = numbers[j - 4]
                second_val = numbers[j - 3]
                if 10 <= first_val <= 80 and 10 <= second_val <= 80:
                    undecided = numbers[j - 2] + numbers[j - 1]
                    _assign(first_val, second_val, undecided)
                    our = poll.our_support
                    opp_val = list(poll.opponent_support.values())[0]
                    logger.info(
                        f"nttId={poll.ntt_id}: {candidate} {our}% vs "
                        f"{opponent} {opp_val}% (undecided {undecided}%)"
                    )
                    return True

        # 합계 100이 없는 경우 (리얼미터/서던포스트 스타일)
        if len(numbers) >= 2:
            for start in range(len(numbers) - 1):
                a, b = numbers[start], numbers[start + 1]
                if 15 <= a <= 65 and 15 <= b <= 65 and 50 <= a + b <= 95:
                    remaining = numbers[start + 2:start + 5]
                    undecided = sum(r for r in remaining if r < 20)
                    _assign(a, b, undecided)
                    our = poll.our_support
                    opp_val = list(poll.opponent_support.values())[0]
                    logger.info(
                        f"nttId={poll.ntt_id} (heuristic): {candidate} {our}% vs "
                        f"{opponent} {opp_val}%"
                    )
                    return True

        return False

    # ──────────────────────────────────────────────
    # 4. 전체 파이프라인
    # ──────────────────────────────────────────────
    def collect_all(self, known_ntt_ids: set[str] | None = None) -> list[NesdcPoll]:
        """
        전체 수집 파이프라인:
        1) 목록 스캔 → 2) 신규만 상세 조회 → 3) PDF 파싱 → 반환
        known_ntt_ids: 이미 DB에 있는 nttId 집합 (중복 방지)
        """
        known = known_ntt_ids or set()
        items = self.scan_list()

        polls: list[NesdcPoll] = []
        for item in items:
            nid = item["ntt_id"]
            if nid in known:
                logger.debug(f"Skip known nttId={nid}")
                continue

            try:
                poll = self.fetch_detail(nid)
                self.parse_poll_pdf(poll)
                # _html 제거 (메모리)
                if hasattr(poll, "_html"):
                    delattr(poll, "_html")
                polls.append(poll)
            except Exception as e:
                logger.error(f"Error processing nttId={nid}: {e}")

        logger.info(f"Collected {len(polls)} new polls ({sum(1 for p in polls if p.pdf_parsed)} with support data)")
        return polls

    def collect_new_and_save(self) -> list[NesdcPoll]:
        """DB에 없는 새 여론조사만 수집하여 저장"""
        try:
            from storage.database import ElectionDB
            db = ElectionDB()

            # 기존 nesdc nttId 조회
            existing = db.get_nesdc_known_ids()
            db.close()
        except Exception:
            existing = set()

        polls = self.collect_all(known_ntt_ids=existing)

        # DB 저장
        saved = 0
        for poll in polls:
            if not poll.pdf_parsed:
                continue
            try:
                from storage.database import ElectionDB
                db = ElectionDB()
                db.save_poll(
                    poll_date=poll.survey_date or poll.pub_date,
                    pollster=f"{poll.org} ({poll.client})",
                    sample_size=poll.sample_size,
                    margin_of_error=poll.margin_of_error,
                    our_support=poll.our_support,
                    opponent_support=poll.opponent_support,
                    undecided=poll.undecided,
                    source=f"nesdc:{poll.ntt_id}",
                )
                db.save_nesdc_id(poll.ntt_id)
                db.close()
                saved += 1
            except Exception as e:
                logger.error(f"DB save failed for nttId={poll.ntt_id}: {e}")

        logger.info(f"Saved {saved} new polls to DB")
        return polls
