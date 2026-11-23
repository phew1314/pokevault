# POKÉVAULT 動畫與音效原始檔

## 抽卡動畫（Blender）
- `blender/make_tex.py`：產生卡背與紙袋印刷貼圖（PIL）
- `blender/scene.py`：建場景＋動畫＋渲染。`python scene.py <intro|bigA|rev> <起始格> <結束格> [samples] [解析度倍率]`
  - 需要 `pip install bpy`（Python 3.11，Blender 5.0.1）
  - 三段影片最後一格構圖必須相同：卡背置中、卡高 = 畫面高 55%（網站 `CinemaEngine.VIDEO.cardFrac`）
  - bigA 第 1–41 格與 intro 相同，可直接複製
- 編碼：`ffmpeg -framerate 24 -i out/<clip>/%04d.png -vf "vignette=PI/5,format=yuv420p" -c:v libx264 -crf 23 -movflags +faststart cinema/<clip>.mp4`
  - bigA 取 124 格、rev 取 112 格

## 音效／背景音樂（numpy 合成）
- `audio/sfx.py`：依影片格數（24fps）對齊的音效 → `audio/sfx_*.mp3`
- `audio/bgm.py`：原創 lo-fi 循環 → `audio/bgm_*.mp3`（檔案前後各有 0.1 秒循環補白，網站用 loopStart/loopEnd 無縫循環；改長度要同步更新 `TownBGM.tracks` 的 loopLen）
