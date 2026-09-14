"""Separate, versioned image indexes. Query and cases share prepare()/encode()."""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import uuid
from pathlib import Path

import numpy as np
import torch
from fastapi import HTTPException
from PIL import Image, ImageOps

from policy import MODES

ROOT = Path(__file__).parent
INDEX_DIR = ROOT / 'data' / 'indexes'
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DINO_ID = 'facebook/dinov3-vitb16-pretrain-lvd1689m'
DINO2_ID = 'facebook/dinov2-base'
INDEX_VERSION = 1
WEIGHTING = 'exp_cosine_x10'
LOCK = threading.RLock()
encoders = {}
indexes = {}


def canonical(image):
    return ImageOps.exif_transpose(image).convert('RGB')


def fingerprint(image):
    rgb = canonical(image)
    return hashlib.sha256(f'{rgb.width}x{rgb.height}:'.encode() + rgb.tobytes()).hexdigest()


def file_hash(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def encoder_kind(mode):
    return mode.split('_')[0] if mode in {'dinov2_roi', 'dinov3_roi'} else 'clip'


def load_encoder(mode):
    kind = encoder_kind(mode)
    with LOCK:
        if kind in encoders:
            return encoders[kind]
        try:
            if kind == 'dinov2':
                from transformers import AutoImageProcessor, AutoModel
                source = os.getenv('DINOV2_MODEL_PATH') or DINO2_ID
                options = {'local_files_only': os.getenv('HF_HUB_OFFLINE', '0') == '1'}
                processor = AutoImageProcessor.from_pretrained(source, **options)
                model = AutoModel.from_pretrained(source, use_safetensors=True, **options).to(DEVICE).eval()
                if model.config.model_type != 'dinov2' or model.config.hidden_size != 768 or model.config.patch_size != 14 or model.config.num_hidden_layers != 12:
                    raise ValueError('Expected DINOv2 ViT-B/14')
                encoders[kind] = (model, processor)
            elif kind == 'dinov3':
                from huggingface_hub import get_token, try_to_load_from_cache
                if not os.getenv('DINOV3_MODEL_PATH') and not get_token() and not isinstance(try_to_load_from_cache(DINO_ID, 'model.safetensors'), str):
                    raise OSError('Authorized DINOv3 weights are not configured')
                from transformers import AutoImageProcessor, AutoModel
                source = os.getenv('DINOV3_MODEL_PATH') or DINO_ID
                options = {'local_files_only': os.getenv('HF_HUB_OFFLINE', '0') == '1'}
                processor = AutoImageProcessor.from_pretrained(source, **options)
                model = AutoModel.from_pretrained(source, **options).to(DEVICE).eval()
                if model.config.model_type != 'dinov3_vit' or model.config.hidden_size != 768 or model.config.patch_size != 16 or model.config.num_hidden_layers != 12:
                    raise ValueError('Expected DINOv3 ViT-B/16')
                encoders[kind] = (model, processor)
            else:
                import open_clip
                model, _, processor = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
                encoders[kind] = (model.to(DEVICE).eval(), processor)
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            message = ('DINOv3 尚未就緒：請提供已授權的 Hugging Face 權重資料夾，或在伺服器設定具存取權的 HF_TOKEN。系統不會自動改用 CLIP。'
                       if kind == 'dinov3' else f'{kind.upper()} 模型載入失敗，請確認模型快取與網路。')
            raise HTTPException(503, message) from error
        return encoders[kind]


def encode(image, mode):
    model, processor = load_encoder(mode)
    with LOCK, torch.inference_mode():
        if mode in {'dinov2_roi', 'dinov3_roi'}:
            inputs = processor(images=canonical(image), return_tensors='pt').to(DEVICE)
            outputs = model(**inputs)
            feature = outputs.last_hidden_state[:, 0, :] if mode == 'dinov2_roi' else outputs.pooler_output
        else:
            feature = model.encode_image(processor(canonical(image)).unsqueeze(0).to(DEVICE))
        vector = feature.float().cpu().numpy().reshape(-1)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(vector).all() or norm <= 1e-12:
        raise ValueError('Invalid image embedding')
    return (vector / norm).tolist()


def prepare(image, mode, detection):
    image = canonical(image)
    if mode == 'clip_full':
        return image, None
    if not detection:
        return None, None
    coords = detection['bbox']
    if len(coords) != 4 or not all(math.isfinite(v) for v in coords):
        return None, None
    x1, y1 = max(0, math.floor(coords[0])), max(0, math.floor(coords[1]))
    x2, y2 = min(image.width, math.ceil(coords[2])), min(image.height, math.ceil(coords[3]))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None, None
    bbox = [x1, y1, x2, y2]
    return image.crop(bbox), bbox


def signature(records, mode, yolo_path):
    import importlib.metadata
    versions = {name: importlib.metadata.version(name) for name in ['torch', 'torchvision', 'pillow', 'ultralytics', 'open-clip-torch', 'transformers']}
    is_dino = mode in {'dinov2_roi', 'dinov3_roi'}
    local_model = os.getenv('DINOV2_MODEL_PATH' if mode == 'dinov2_roi' else 'DINOV3_MODEL_PATH')
    local_files = []
    if is_dino and local_model and Path(local_model).is_dir():
        local_files = [(p.name, file_hash(p)) for p in sorted(Path(local_model).glob('*')) if p.is_file()]
    revision = getattr(load_encoder(mode)[0].config, '_commit_hash', None) if is_dino else None
    payload = {'version': INDEX_VERSION, 'mode': mode, 'versions': versions, 'resolved_revision': revision,
               'encoder': DINO2_ID if mode == 'dinov2_roi' else DINO_ID if mode == 'dinov3_roi' else 'ViT-B-32/laion2b_s34b_b79k',
               'local_model': local_files, 'roi': 'floor-ceil-clamp-primary-confidence-v1',
               'yolo': file_hash(yolo_path) if mode != 'clip_full' and yolo_path.exists() else None,
               'cases': [(r, file_hash(ROOT / r['image']) if (ROOT / r['image']).is_file() else None) for r in records]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def build_index(records, mode, detect, yolo_path, force=False):
    with LOCK:
        sig = signature(records, mode, yolo_path)
        path = INDEX_DIR / f'{mode}_embeddings.json'
        if not force and mode in indexes and indexes[mode]['signature'] == sig:
            return indexes[mode]
        if not force and path.exists():
            try:
                saved = json.loads(path.read_text(encoding='utf-8'))
                if saved['signature'] == sig and saved['mode'] == mode:
                    expected_dim = 768 if mode in {'dinov2_roi', 'dinov3_roi'} else 512
                    if saved['dimension'] == expected_dim and all(len(r['embedding']) == expected_dim and np.isfinite(r['embedding']).all() and abs(np.linalg.norm(r['embedding']) - 1) < 1e-4 for r in saved['records']):
                        indexes[mode] = saved
                        return saved
            except (ValueError, KeyError, TypeError):
                pass
        load_encoder(mode)
        valid, failures = [], []
        for record in records:
            try:
                with Image.open(ROOT / record['image']) as opened:
                    image = canonical(opened)
                detection = detect(image, save=False)['detection'] if mode != 'clip_full' else None
                prepared, bbox = prepare(image, mode, detection)
                if prepared is None:
                    failures.append({'case_id': record['id'], 'embedding_status': 'no_detection'})
                    continue
                rate = float(record['wear_rate'])
                if not math.isfinite(rate) or not 0 <= rate <= 1:
                    raise ValueError('Invalid wear label')
                valid.append({**record, 'embedding': encode(prepared, mode), 'fingerprint': fingerprint(image),
                              'file_hash': file_hash(ROOT / record['image']), 'roi_bbox': bbox, 'embedding_status': 'ready'})
            except (OSError, ValueError) as error:
                failures.append({'case_id': record['id'], 'embedding_status': 'failed', 'reason': type(error).__name__})
        result = {'mode': mode, **MODES[mode], 'signature': sig, 'dimension': 768 if mode in {'dinov2_roi', 'dinov3_roi'} else 512,
                  'records': valid, 'failures': failures, 'source_count': len(records), 'version': INDEX_VERSION}
        atomic_json(path, result)
        indexes[mode] = result
        return result


def retrieve(vector, records, query_fingerprint, query_id=None, query_file_hash=None):
    candidates, excluded = [], []
    for case in records:
        if case['fingerprint'] == query_fingerprint or (query_id and case['id'] == query_id) or (query_file_hash and case.get('file_hash') == query_file_hash):
            excluded.append(case['id'])
            continue
        score = float(np.clip(np.dot(vector, case['embedding']), -1, 1))
        candidates.append({**case, 'similarity': score})
    top = sorted(candidates, key=lambda c: (-c['similarity'], c['id']))[:5]
    public = [{k: v for k, v in c.items() if k not in {'embedding', 'fingerprint', 'file_hash'}} for c in top]
    for rank, case in enumerate(public, 1):
        from urllib.parse import quote
        case.update(rank=rank, case_id=case['id'], image_url=f"/api/case-image/{quote(case['id'], safe='')}", wear_percent=case['wear_rate'] * 100)
    similarity = float(np.mean([c['similarity'] for c in top])) if top else None
    std = float(np.std([c['wear_rate'] * 100 for c in top])) if top else None
    wear = None
    if len(top) == 5:
        weights = np.exp(np.array([c['similarity'] for c in top]) * 10)
        wear = float(np.dot(weights, [c['wear_rate'] * 100 for c in top]) / weights.sum())
    return {'predicted_wear_percent': wear, 'average_similarity': similarity, 'wear_std_percent': std,
            'top_k': public, 'excluded_case_ids': excluded, 'excluded_self_match': True, 'weighting': WEIGHTING}


def index_summary(index):
    return {k: v for k, v in index.items() if k != 'records'} | {'indexed_count': len(index['records'])}
