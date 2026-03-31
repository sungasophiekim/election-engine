"""데일리 전략 리포트 PDF 생성"""
import os
from pathlib import Path
from fpdf import FPDF

_FONT_DIR = Path(__file__).resolve().parent / "fonts"


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("NotoSans", "", str(_FONT_DIR / "NotoSansKR-Regular.ttf"), uni=True)
        self.add_font("NotoSans", "B", str(_FONT_DIR / "NotoSansKR-Bold.ttf"), uni=True)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("NotoSans", "B", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, "김경수 경남도지사 캠프 · 대외비", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("NotoSans", "", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Election Engine · {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.set_font("NotoSans", "B", 12)
        self.set_text_color(13, 27, 42)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(36, 87, 164)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def sub_title(self, title: str):
        self.set_font("NotoSans", "B", 10)
        self.set_text_color(36, 87, 164)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str, indent: int = 0):
        self.set_font("NotoSans", "", 9)
        self.set_text_color(50, 50, 50)
        if indent:
            self.set_x(self.l_margin + indent)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def bullet(self, text: str, indent: int = 5):
        self.set_font("NotoSans", "", 9)
        self.set_text_color(50, 50, 50)
        self.set_x(self.l_margin + indent)
        self.multi_cell(0, 5, f"• {text}")

    def badge(self, text: str, color: tuple = (36, 87, 164)):
        self.set_font("NotoSans", "B", 8)
        self.set_fill_color(*color)
        self.set_text_color(255, 255, 255)
        w = self.get_string_width(text) + 6
        self.cell(w, 5, text, fill=True, new_x="END")
        self.set_text_color(50, 50, 50)


def generate_pdf(rpt: dict) -> bytes:
    """리포트 JSON → PDF bytes"""
    pdf = ReportPDF()
    pdf.add_page()

    # 제목
    pdf.set_font("NotoSans", "B", 16)
    pdf.set_text_color(13, 27, 42)
    pdf.cell(0, 10, "경남도지사 선거 전략대응 리포트", new_x="LMARGIN", new_y="NEXT")

    date = rpt.get("date", "")
    d_day = rpt.get("d_day", "?")
    theme = rpt.get("daily_theme", {})
    theme_kw = theme.get("keyword", theme.get("theme", ""))

    pdf.set_font("NotoSans", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"{date} · D-{d_day} · 대외비", new_x="LMARGIN", new_y="NEXT")
    if theme_kw:
        pdf.set_font("NotoSans", "B", 10)
        pdf.set_text_color(200, 146, 42)
        pdf.cell(0, 6, f"테마: {theme_kw}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # 1. 핵심 진단
    pdf.section_title("1. 핵심 진단 — 종합 브리핑")
    summary = rpt.get("executive_summary", "")
    pdf.body_text(summary)

    # 지수 표시
    indices = rpt.get("beta_reference", {})
    if indices:
        issue = indices.get("issue_index", indices.get("leading_index", 50))
        reaction = rpt.get("situation_diagnosis", {}).get("indices", {}).get("reaction_index", 50)
        pandse = indices.get("pandse_index", indices.get("leading_index", 50))
        pdf.set_font("NotoSans", "B", 9)
        pdf.set_text_color(13, 27, 42)
        pdf.cell(60, 6, f"이슈지수 {issue}pt", border=1, align="C")
        pdf.cell(60, 6, f"반응지수 {reaction}pt", border=1, align="C")
        pdf.cell(60, 6, f"판세지수 {pandse}pt", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # 긴급 액션
    urgent = [e for e in rpt.get("execution", []) if "즉시" in e.get("when", e.get("time", "")) or "오늘" in e.get("when", e.get("time", ""))]
    if urgent:
        pdf.sub_title("오늘 반드시 해야 할 것")
        nums = "①②③④⑤"
        for i, e in enumerate(urgent[:3]):
            what = e.get("what", e.get("task", ""))
            pdf.bullet(f"{nums[i]} {what}")
        pdf.ln(2)

    # 후보 진단
    sd = rpt.get("situation_diagnosis", {})
    our = sd.get("our_candidate", sd.get("our_candidate", ""))
    opp = sd.get("opp_candidate", sd.get("opponent", ""))
    if our or opp:
        pdf.sub_title("우리 후보 진단")
        if our:
            pdf.body_text(our, indent=3)
        pdf.sub_title("상대 후보 진단")
        if opp:
            pdf.body_text(opp, indent=3)

    # 2. 이슈 분석
    issues = sd.get("issue_state", [])
    if issues:
        pdf.section_title("2. 이슈 분석 — 무엇이 확산되고, 어떻게 반응하는가")
        for i, iss in enumerate(issues[:10]):
            side = iss.get("side", "")
            side_mark = "🔵" if "우리" in str(side) else "🔴" if "상대" in str(side) else "⚪"
            name = iss.get("name", "")
            count = iss.get("count", 0)
            spreading = iss.get("spreading", "")
            diagnosis = iss.get("diagnosis", "")
            pdf.set_font("NotoSans", "B", 9)
            pdf.set_text_color(13, 27, 42)
            pdf.cell(0, 5, f"{i+1}. {name} ({count}건) — {side} · {spreading}", new_x="LMARGIN", new_y="NEXT")
            if diagnosis:
                pdf.body_text(f"   {diagnosis}", indent=5)

    # 3. 대응 전략
    strategies = rpt.get("strategies", [])
    if strategies:
        pdf.section_title("3. 대응 전략 — 조건 기반 실행 방안")

        dl = rpt.get("decision_layer", {})
        moment = dl.get("moment_type", dl.get("phase", ""))
        if moment:
            pdf.set_font("NotoSans", "B", 10)
            pdf.set_text_color(13, 27, 42)
            pdf.cell(0, 6, f"현재 국면: {moment}", new_x="LMARGIN", new_y="NEXT")
            protect = dl.get("must_protect", dl.get("defend", ""))
            push = dl.get("can_push", dl.get("push", ""))
            if protect:
                pdf.bullet(f"지켜야 할 것: {protect}")
            if push:
                pdf.bullet(f"밀어볼 것: {push}")
            pdf.ln(3)

        for s in strategies:
            timeline = s.get("timeline", "")
            is_urgent = "즉시" in timeline or "오늘" in timeline
            pdf.set_font("NotoSans", "B", 9)
            color = (192, 57, 43) if is_urgent else (36, 87, 164)
            pdf.set_text_color(*color)
            label = "긴급" if is_urgent else "중장기"
            pdf.cell(0, 6, f"[{label}] {s.get('title', '')} — {timeline}", new_x="LMARGIN", new_y="NEXT")
            if s.get("condition"):
                pdf.body_text(f"조건: {s['condition']}", indent=3)
            if s.get("action"):
                pdf.body_text(s["action"], indent=3)
            if s.get("target"):
                pdf.body_text(f"타겟: {s['target']}", indent=3)
            if s.get("risk"):
                pdf.set_text_color(192, 57, 43)
                pdf.body_text(f"리스크: {s['risk']}", indent=3)
            pdf.ln(1)

    # 4. 현장 방문 일정
    schedule = rpt.get("field_schedule", [])
    if schedule:
        pdf.section_title("4. 현장 방문 일정")
        if theme.get("reason", theme.get("rationale", "")):
            pdf.set_font("NotoSans", "B", 9)
            pdf.set_text_color(200, 146, 42)
            pdf.cell(0, 6, f"TODAY'S THEME: {theme_kw}", new_x="LMARGIN", new_y="NEXT")
            pdf.body_text(theme.get("reason", theme.get("rationale", "")))
            pdf.ln(2)

        for i, s in enumerate(schedule):
            region = s.get("region", "")
            time_str = s.get("when", s.get("time", ""))
            loc = s.get("location", "")
            concept = s.get("concept", "")
            message = s.get("message", "")
            target = s.get("target_segment", s.get("target", ""))
            media = s.get("media_plan", s.get("media", ""))
            caution = s.get("caution", "")
            kpi = s.get("kpi", "")

            pdf.set_font("NotoSans", "B", 10)
            pdf.set_text_color(36, 87, 164)
            pdf.cell(0, 7, f"PRIORITY {i+1} | {time_str} | {region}", new_x="LMARGIN", new_y="NEXT")
            if loc:
                pdf.body_text(f"장소: {loc}", indent=3)
            if concept:
                pdf.body_text(f"컨셉: {concept}", indent=3)
            if message:
                pdf.set_font("NotoSans", "B", 9)
                pdf.set_text_color(13, 27, 42)
                pdf.set_x(pdf.l_margin + 3)
                pdf.multi_cell(0, 5, f'"{message}"')
                pdf.ln(1)
            if target:
                pdf.body_text(f"타겟: {target}", indent=3)
            if media:
                pdf.body_text(f"미디어: {media}", indent=3)
            if caution:
                pdf.set_text_color(192, 57, 43)
                pdf.body_text(f"주의: {caution}", indent=3)
            if kpi:
                pdf.body_text(f"KPI: {kpi}", indent=3)
            pdf.ln(2)

    # 5. 실행 일정
    execution = rpt.get("execution", [])
    if execution:
        pdf.section_title("5. 실행 일정 & KPI")
        for e in execution:
            when = e.get("when", e.get("time", ""))
            what = e.get("what", e.get("task", ""))
            who = e.get("who", e.get("owner", ""))
            kpi = e.get("kpi", "")
            pdf.set_font("NotoSans", "B", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(45, 5, when, border="B")
            pdf.set_font("NotoSans", "", 8)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(0, 5, f"{what} | {who} | KPI: {kpi}", border="B", new_x="LMARGIN", new_y="NEXT")

    # 6. 위기 관리
    risks = rpt.get("risk_management", [])
    if risks:
        pdf.ln(3)
        pdf.section_title("위기 관리 매트릭스")
        for r in risks:
            pdf.set_font("NotoSans", "B", 9)
            pdf.set_text_color(192, 57, 43)
            pdf.cell(0, 5, r.get("risk", ""), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(50, 50, 50)
            pdf.set_font("NotoSans", "", 8)
            if r.get("trigger"):
                pdf.body_text(f"트리거: {r['trigger']}", indent=3)
            if r.get("response"):
                pdf.body_text(f"대응: {r['response']}", indent=3)
            if r.get("owner"):
                pdf.body_text(f"담당: {r['owner']}", indent=3)
            pdf.ln(1)

    # 푸터
    pdf.ln(5)
    pdf.set_font("NotoSans", "", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 4, f"김경수 경남도지사 캠프 · 전략대응 {date} 리포트 · D-{d_day} · 대외비", align="C")

    return pdf.output()
