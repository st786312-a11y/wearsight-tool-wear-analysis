# WearSight 刀具 ROI 磨耗分析

啟動：`docker compose up -d --build`，開啟 [本機介面](http://localhost:8080)。

## 目前流程

```text
圖片 → EXIF 方向校正 → YOLO 偵測 → 主要框裁切 ROI
     → DINOv2 ViT-B/14 → CLS token → L2 normalized embedding
     → cosine similarity → 排除自身 → Top-5
     → 指數相似度加權磨耗率 → 品質檢查 → 狀態與建議
     → 完整分析快照 → 網頁／Dify／Ollama 問答
```

可明確選擇的模式：

| mode | 影像 | 編碼器 | 用途 |
|---|---|---|---|
| `dinov2_roi` | YOLO ROI | DINOv2 ViT-B/14 | 目前預設，官方公開權重 |
| `dinov3_roi` | YOLO ROI | DINOv3 ViT-B/16 | 保留選項，需已授權權重 |
| `clip_roi` | YOLO ROI | OpenCLIP ViT-B/32 | ROI 比較基準 |
| `clip_full` | 完整原圖 | OpenCLIP ViT-B/32 | 整圖比較基準 |

目前改用 DINOv2。模型來源為 [facebook/dinov2-base](https://huggingface.co/facebook/dinov2-base)，使用 768 維 CLS 特徵與獨立 `dinov2_roi_embeddings.json` 索引，首次下載後保存在 Docker 持久快取。可於 `.env` 設定 `DINOV2_MODEL_PATH` 指向已掛載的官方 Hugging Face 模型資料夾。

DINOv3 尚未提供授權權重，該模式仍回傳 503，不會自動切模型。CLIP 比較模式保留。

## 取得 DINOv3 權重

採用官方 [facebook/dinov3-vitb16-pretrain-lvd1689m](https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m)。官方文件提供 Transformers 的 `AutoImageProcessor`、`AutoModel` 和 `pooler_output` 用法，模型受存取授權限制。

使用者需自行在官方模型頁完成申請與授權。不要將權杖貼入對話、程式碼或提交到版本庫。

取得後可選擇：

1. 在本機專案 `.env` 設定具有該模型讀取權的 `HF_TOKEN`，再執行 `docker compose up -d api`。
2. 將官方 Hugging Face 格式的完整模型資料夾放入 `backend/models/dinov3-vitb16/`，於 `.env` 設定 `DINOV3_MODEL_PATH=/app/yolo/dinov3-vitb16`。資料夾需含模型 config、影像 processor config 與 safetensors 權重。單獨的官方 PyTorch `.pth` 不適用此載入介面。

在設定頁按「檢查模型」→「重建索引」→「比較檢索模式」。本系統只執行推論，不需要訓練 DINOv3。

## 索引與一致性

- Query 和歷史案例共用 `canonical → prepare → encode`，ROI 從原始像素裁切，不使用畫框後的圖。
- 依最高偵測信心度選主要框，向下／向上取整並限制於影像範圍。框太小或無偵測的 ROI 案例記為 `no_detection`，不混入完整原圖。
- 獨立索引位於 `backend/data/indexes/{mode}_embeddings.json`，含 L2 正規化向量、維度、模型、來源、影像雜湊、ROI 框、版本簽章與失敗清單。目前案例量小，使用精確向量比對，無需 FAISS。
- 簽章包含案例資料與影像 SHA-256、YOLO 權重、前處理規則、套件版本及 DINOv3 模型版本。案例、權重或版本變動時會重新建索引。
- 排除相同 case_id、原檔 SHA-256 或校正後 RGB 像素雜湊。重新壓縮／裁切後的近似圖片不保證被視為自身。
- 保留原程式的公式：`weight_i = exp(cosine_i * 10)`，`predicted_wear = sum(weight_i * wear_i) / sum(weight_i)`。所有模式一致；沒有改成分類器或直接相似度加權。
- Top-K 固定 5；不足五筆時不產生磨耗率。磨耗標準差由實際檢索案例的標籤以母體標準差計算，單位為百分點。

## 判定與問答

`backend/policy.py` 是唯一判定來源。設定保存在 `backend/data/settings.json`：

| 條件 | 預設值 |
|---|---|
| 刀具偵測信心度下限 | 0.50 |
| 平均相似度下限 | 0.85（尚待依模型校準） |
| Top-5 磨耗標準差上限 | 20 百分點 |
| 中度磨耗門檻 | 40% |
| 更換／停機門檻 | 80% |

品質不足優先判為 `manual_review`；全部通過後，磨耗率 >= 更換門檻為 `replace_or_stop`，否則 `continue`。中度門檻影響磨耗程度和建議文字，不另行覆寫品質判定。所有判断使用未四捨五入的數值。

移除舊的 40%／75% 前端判斷及由相似度裁切成的「分析信心度」。YOLO 信心度與相似度都不是磨耗率預測準確率。初始畫面不再顯示示意結果。

`POST /api/assistant` 只接受 `analysis_id`、`question`，以後端已保存的完整分析快照回答。人工覆核結果由系統直接說明；其他結果可由 Ollama 補充，無法連線則提供系統建議。LLM 文字不是狀態判定來源。

## API 與 Dify

- `POST /api/analyze`：multipart `image`，或 JSON `image_url`；可選 `mode`、`case_id`、`question`。
- `POST /api/models/load`：JSON `{"mode":"dinov3_roi"}`，檢查模型可載入。
- `POST /api/indexes/rebuild`：JSON `{"mode":"clip_roi"}`，強制重建指定索引。
- `GET /api/indexes`：最後建立的索引摘要與排除紀錄；是否過期會在下次檢索時重新驗證。
- `GET /api/validate`：以共同候選案例與共同查詢集合比較檢索模式，結果保存於 `backend/data/evaluation.json`。
- `GET /api/analyses/{analysis_id}`：完整分析快照，包括門檻、ROI、Top-5 與狀態。
- `GET /api/health`：服務及模型載入狀態，不把服務存活當成模型已可用。
- 案例、設定、歷史 API 保留。新增案例磨耗率仍採 0–1，前端表單以百分比輸入後轉換。移除案例只移除登錄，保留原始圖片。

既有 Dify 作為獨立入口保留，網頁目前直接走 FastAPI。詳見 [Dify 節點遷移說明](dify/README.md)。Dify 線上已發布工作流需另行更新節點，修改本地文件不會自動發布。

## 驗證

在後端容器執行 `python -m unittest test_pipeline -v`。測試只寫入隔離暫存目錄。

比較指標包含 MAE、RMSE、Top-1 磨耗絕對差、Top-5 磨耗標準差、平均相似度與 self-match exclusion。誤差均採百分點。

這是留一影像驗證，尚未按實體刀具／拍攝批次分組。資料集若有同一刀具的多張近似照片，可能高估泛化能力。DINOv3 未就緒時，仍回傳 DINOv2 與 CLIP 等可用模式的比較與未就緒原因，不產生 DINOv3 分數。待 DINOv3 取得權重後，以同一資料重新比較。
