"""실투표 예측 API — legacy 엔진 호출"""
from fastapi import APIRouter
from data.poll_data import get_latest_poll

router = APIRouter(prefix="/api/prediction", tags=["prediction"])


@router.get("")
def get_prediction():
    try:
        import sys
        sys.path.insert(0, "/Users/sunga/Desktop/election_engine")
        from engines.turnout_predictor import predict_turnout
        result = predict_turnout()
        d = result.to_dict()
        base = d.get("base", {})
        corr = d.get("correction", {})

        computed_at = d.get("computed_at", "")
        return {
            "poll": get_latest_poll(),
            "base": {
                "kim": base.get("kim_pct", 50),
                "park": base.get("park_pct", 50),
                "gap": base.get("gap", 0),
                "turnout": base.get("total_turnout", 0),
                "by_age": base.get("by_age", []),
                "updated_at": computed_at,
            },
            "dynamic": {
                "kim": corr.get("dynamic_kim", 50),
                "park": corr.get("dynamic_park", 50),
                "gap": corr.get("dynamic_gap", 0),
                "pandse_index": corr.get("pandse_index", 50),
                "pandse_gap": corr.get("pandse_gap", 0),
                "mix": corr.get("mix", ""),
                "d_day": corr.get("d_day", 0),
                "factors": corr.get("factors", []),
                "updated_at": computed_at,
            },
        }
    except Exception as e:
        return {"error": str(e), "poll": get_latest_poll(), "base": {}, "dynamic": {}}
