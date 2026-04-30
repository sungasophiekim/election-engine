"""여론조사 데이터 — 역대 득표율 + 9대 여론조사"""

POLL_DATA = [
    # 역대 실제 득표
    {"label": "6기 지선", "date": "2014", "kim": 36.0, "park": 59.4, "type": "election"},
    {"label": "7기 지선", "date": "2018", "kim": 52.8, "park": 43.5, "type": "election"},
    {"label": "8기 지선", "date": "2022", "kim": 30.0, "park": 65.7, "type": "election"},
    # 9대 여론조사
    {"label": "MBC경남(KSOI)", "date": "25.09", "kim": 39.5, "park": 44.0, "type": "poll"},
    {"label": "경남신문(한국갤럽)", "date": "25.10", "kim": 31.0, "park": 39.0, "type": "poll"},
    {"label": "MBC경남(KSOI)", "date": "25.11", "kim": 36.0, "park": 35.5, "type": "poll"},
    {"label": "경남매일(모노커뮤)", "date": "25.12", "kim": 35.0, "park": 45.0, "type": "poll"},
    {"label": "경남신문(한국갤럽)", "date": "25.12", "kim": 43.0, "park": 45.0, "type": "poll"},
    {"label": "부산일보(KSOI)", "date": "26.01", "kim": 38.5, "park": 38.5, "type": "poll"},
    {"label": "KBS(케이스텟)", "date": "26.02", "kim": 29.5, "park": 29.5, "type": "poll"},
    {"label": "KNN(서던포스트)", "date": "26.03", "kim": 36.0, "park": 34.0, "type": "poll"},
    {"label": "세계일보(한국갤럽)", "date": "26.04", "kim": 44.0, "park": 40.0, "type": "poll"},
    {"label": "KBS창원(한국리서치)", "date": "26.04", "kim": 37.0, "park": 27.0, "type": "poll"},
    {"label": "MBC경남(KSOI)", "date": "26.04", "kim": 46.9, "park": 35.7, "type": "poll"},
]


def get_latest_poll() -> dict:
    return POLL_DATA[-1]


# 한국갤럽 전국 정당 지지율 + 대통령 지지율
NATIONAL_POLL_TREND = [
    {"date": "25.07", "label": "25년7월", "president": 64, "dem": 45, "ppp": 20},
    {"date": "25.12", "label": "25년12월", "president": 58, "dem": 41, "ppp": 25},
    {"date": "26.01", "label": "26년1월1주", "president": 60, "dem": 45, "ppp": 26},
    {"date": "26.02", "label": "26년2월2주", "president": 63, "dem": 44, "ppp": 22},
    {"date": "26.03", "label": "26년3월1주", "president": 65, "dem": 46, "ppp": 21},
    {"date": "26.04", "label": "26년4월1주", "president": 67, "dem": 48, "ppp": 18},
    {"date": "26.04", "label": "26년4월2주", "president": 67, "dem": 48, "ppp": 20},
    {"date": "26.04", "label": "26년4월3주", "president": 66, "dem": 48, "ppp": 19},
    {"date": "26.04", "label": "26년4월4주", "president": 67, "dem": 48, "ppp": 20},
]
