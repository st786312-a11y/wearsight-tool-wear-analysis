"""The single source of operational thresholds for API, UI, Dify and Q&A."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Mode = Literal['dinov2_roi', 'dinov3_roi', 'clip_roi', 'clip_full']
MODES = {
    'dinov2_roi': {'model': 'DINOv2 ViT-B/14', 'image_source': 'yolo_roi'},
    'dinov3_roi': {'model': 'DINOv3 ViT-B/16', 'image_source': 'yolo_roi'},
    'clip_roi': {'model': 'OpenCLIP ViT-B/32', 'image_source': 'yolo_roi'},
    'clip_full': {'model': 'OpenCLIP ViT-B/32', 'image_source': 'full_image'},
}


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    retrieval_mode: Mode = 'dinov2_roi'
    top_k: Literal[5] = 5
    detection_threshold: float = Field(default=0.5, ge=0, le=1)
    similarity_threshold: float = Field(default=0.85, ge=-1, le=1)
    wear_std_threshold: float = Field(default=20, ge=0, le=100)
    moderate_threshold: float = Field(default=40, ge=0, le=100)
    replace_threshold: float = Field(default=80, gt=0, le=100)

    @model_validator(mode='after')
    def ordered_thresholds(self):
        if self.moderate_threshold >= self.replace_threshold:
            raise ValueError('中度磨耗門檻必須低於更換門檻。')
        return self


def assess(wear, detection_confidence, similarity, wear_std, count, settings, extra_reasons=()):
    reasons = list(extra_reasons)
    if detection_confidence is None:
        reasons.append('未偵測到刀具，請人工確認影像與框選區域。')
    elif detection_confidence < settings.detection_threshold:
        reasons.append(f'刀具偵測信心度 {detection_confidence:.3f}，低於設定下限 {settings.detection_threshold:g}。')
    if count < 5:
        reasons.append(f'排除自身後只有 {count} 筆有效案例，需完整 5 筆才能估算磨耗率。')
    if similarity is None or not math.isfinite(similarity):
        reasons.append('目前無法計算相似案例的平均相似度。')
    elif similarity < settings.similarity_threshold:
        reasons.append(f'平均相似度 {similarity:.3f}，低於設定下限 {settings.similarity_threshold:g}。')
    if wear_std is None or not math.isfinite(wear_std):
        reasons.append('目前無法計算相似案例的磨耗標準差。')
    elif wear_std > settings.wear_std_threshold:
        reasons.append(f'Top-5 磨耗標準差為 {wear_std:.2f} 個百分點，超過設定上限 {settings.wear_std_threshold:g}；相似圖片的磨耗標籤差異較大，預估磨耗率僅供參考。')
    if wear is None or not math.isfinite(wear):
        reasons.append('目前沒有可用的磨耗率估算。')
    if reasons:
        status, label, recommendation = 'manual_review', '需人工覆核', '人工確認後再決定是否使用'
    elif wear >= settings.replace_threshold:
        status, label, recommendation = 'replace_or_stop', '建議更換或停機', '停機檢查或更換刀具'
        reasons = ['預估磨耗率已達設定的更換門檻。']
    else:
        status, label = 'continue', '可持續觀察'
        recommendation = '降低負載並安排檢查' if wear >= settings.moderate_threshold else '定期檢查磨耗'
        reasons = ['分析品質通過設定條件，預估磨耗率尚未達更換門檻。']
    level = '無法估算' if wear is None else ('嚴重' if wear >= settings.replace_threshold else '中度' if wear >= settings.moderate_threshold else '輕微')
    return {
        'status': status, 'status_label': label, 'reasons': list(dict.fromkeys(reasons)),
        'status_reason': ' '.join(dict.fromkeys(reasons)),
        'assessment': {'level': level, 'availability': label, 'recommendation': recommendation,
                       'description': ' '.join(dict.fromkeys(reasons))},
        'thresholds': settings.model_dump(),
    }
