#!/bin/zsh
# 換圖：把圖片丟進 images/ 資料夾，執行 ./update.sh 就會更新輪播並上線
cd "$(dirname "$0")"
python3 - <<'PY'
import os,json
exts=('.jpg','.jpeg','.png','.gif','.webp')
fs=sorted(f for f in os.listdir('images') if f.lower().endswith(exts) and not f.startswith('.'))
json.dump(fs,open('images.json','w'),ensure_ascii=False)
print(len(fs),'張圖:',fs)
PY
touch .nojekyll
git add -A
git diff --cached --quiet && { echo "沒有變動"; exit 0; }
git commit -qm "update banners" && git push -q && echo "已推送，約 1 分鐘後生效"
