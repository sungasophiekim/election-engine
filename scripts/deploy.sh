#!/bin/bash
# 배포 스크립트 — 데이터 포함 커밋 + push
cd "$(dirname "$0")/.."

echo "=== 데이터 동기화 ==="
git add -f data/enrichment_snapshot.json \
         data/indices_history.json \
         data/daily_reports/ \
         data/training_data/

# 변경사항 있으면 커밋
if ! git diff --cached --quiet; then
  git commit -m "데이터 동기화 — $(date +%Y-%m-%d\ %H:%M)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  echo "✅ 데이터 커밋 완료"
else
  echo "📋 데이터 변경 없음"
fi

echo "=== Push ==="
git push origin main
echo "✅ 배포 완료 — Render auto-deploy 시작"
