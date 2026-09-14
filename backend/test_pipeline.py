"""Regression tests use isolated files and controlled vectors; never production data."""
import json
import math
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from types import SimpleNamespace
from PIL import Image
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
import retrieval
from evaluation import evaluate
from policy import Settings, assess


def cases(count=7):
    return [{'id': f'case{i}', 'image': f'{i}.png', 'wear_rate': i / 10,
             'fingerprint': f'fp{i}', 'file_hash': f'hash{i}',
             'embedding': [math.cos(i / 10), math.sin(i / 10)]} for i in range(count)]


class PolicyTests(unittest.TestCase):
    def test_boundaries_and_priority(self):
        settings = Settings()
        self.assertEqual(assess(80, .5, .85, 20, 5, settings)['status'], 'replace_or_stop')
        self.assertEqual(assess(79.9999, .5, .85, 20, 5, settings)['status'], 'continue')
        for conf, sim, std, count in [(None, .9, 10, 5), (.499, .9, 10, 5), (.9, .8499, 10, 5), (.9, .9, 20.001, 5), (.9, .9, 10, 4)]:
            self.assertEqual(assess(95, conf, sim, std, count, settings)['status'], 'manual_review')

    def test_settings_control_both_level_and_status(self):
        value = assess(60, .9, .9, 10, 5, Settings(moderate_threshold=25, replace_threshold=55))
        self.assertEqual(value['status'], 'replace_or_stop')
        self.assertEqual(value['assessment']['level'], '嚴重')
        self.assertEqual(value['thresholds']['replace_threshold'], 55)

    def test_invalid_settings(self):
        for data in [{'top_k': 4}, {'moderate_threshold': 90}, {'similarity_threshold': float('nan')}, {'model':'DINOv2'}]:
            with self.assertRaises(ValidationError):
                Settings(**data)


class RetrievalTests(unittest.TestCase):
    def test_dinov2_uses_cls_token_and_normalizes_separately(self):
        class Inputs(dict):
            def to(self, device):
                return self
        def processor(**kwargs):
            return Inputs()
        def model(**kwargs):
            return SimpleNamespace(last_hidden_state=torch.tensor([[[3., 4.], [9., 0.]]]))
        with patch.object(retrieval, 'load_encoder', return_value=(model, processor)):
            vector = retrieval.encode(Image.new('RGB', (14, 14)), 'dinov2_roi')
        np.testing.assert_allclose(vector, [.6, .8], atol=1e-6)
        self.assertEqual(retrieval.encoder_kind('dinov2_roi'), 'dinov2')
        self.assertEqual(retrieval.encoder_kind('dinov3_roi'), 'dinov3')
        self.assertEqual(retrieval.encoder_kind('clip_roi'), 'clip')

    def test_weighting_and_std(self):
        rows = cases(5)
        result = retrieval.retrieve([1, 0], rows, 'other')
        weights = np.exp(np.array([math.cos(i / 10) for i in range(5)]) * 10)
        self.assertAlmostEqual(result['predicted_wear_percent'], np.dot(weights, [0, 10, 20, 30, 40]) / weights.sum())
        self.assertAlmostEqual(result['wear_std_percent'], np.std([0, 10, 20, 30, 40]))
        self.assertNotIn('embedding', result['top_k'][0])

    def test_exclude_by_id_pixels_and_file_hash(self):
        rows = cases(8)
        rows[1]['fingerprint'] = rows[0]['fingerprint']
        result = retrieval.retrieve([1, 0], rows, 'fp0', 'case2', 'hash3')
        self.assertEqual(set(result['excluded_case_ids']), {'case0', 'case1', 'case2', 'case3'})
        self.assertIsNone(result['predicted_wear_percent'])
        self.assertEqual(len(result['top_k']), 4)

    def test_crop_uses_original_pixels_and_clamps(self):
        image = Image.new('RGB', (10, 10), (2, 3, 4))
        roi, bbox = retrieval.prepare(image, 'dinov3_roi', {'bbox': [-1.2, 2.8, 12, 8.2]})
        self.assertEqual(bbox, [0, 2, 10, 9])
        self.assertEqual(roi.size, (10, 7))
        self.assertEqual(roi.getpixel((0, 0)), (2, 3, 4))
        self.assertEqual(retrieval.prepare(image, 'clip_roi', None), (None, None))
        self.assertEqual(retrieval.prepare(image, 'dinov3_roi', {'bbox':[8, 8, 2, 2]}), (None, None))
        self.assertEqual(retrieval.prepare(image, 'clip_full', None)[0].size, (10, 10))

    def test_fingerprint_includes_dimensions_and_ignores_filename(self):
        a, b = Image.new('RGB', (2, 6)), Image.new('RGB', (3, 4))
        self.assertNotEqual(retrieval.fingerprint(a), retrieval.fingerprint(b))
        self.assertEqual(retrieval.fingerprint(a), retrieval.fingerprint(a.copy()))

    def test_index_excludes_missing_roi_and_isolates_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new('RGB', (10, 10)).save(root / 'a.png')
            records = [{'id':'a', 'image':'a.png', 'wear_rate':.5}]
            with patch.object(retrieval, 'ROOT', root), patch.object(retrieval, 'INDEX_DIR', root / 'indexes'), patch.object(retrieval, 'indexes', {}), patch.object(retrieval, 'signature', side_effect=lambda r, m, y:m), patch.object(retrieval, 'load_encoder'), patch.object(retrieval, 'encode', return_value=[1.0]+[0.0]*511):
                detect = lambda image, save: {'detection':None}
                roi = retrieval.build_index(records, 'clip_roi', detect, root / 'yolo.pt')
                full = retrieval.build_index(records, 'clip_full', detect, root / 'yolo.pt')
                self.assertEqual(roi['records'], [])
                self.assertEqual(roi['failures'][0]['embedding_status'], 'no_detection')
                self.assertEqual(len(full['records']), 1)
                self.assertTrue((root / 'indexes/clip_roi_embeddings.json').exists())
                self.assertTrue((root / 'indexes/clip_full_embeddings.json').exists())

    def test_evaluation_uses_common_pool_and_excludes_duplicates(self):
        rows = cases(8)
        rows[1]['fingerprint'] = rows[0]['fingerprint']
        def get_index(mode):
            pool = rows if mode == 'clip_full' else rows[:-1]
            return {'records':pool, 'signature':mode, 'failures':[]}
        report = evaluate(get_index)
        self.assertEqual(len(report['common_candidate_ids']), 7)
        for result in report['models'].values():
            self.assertEqual(result['sample_count'], 7)
            for row in result['results']:
                self.assertNotIn('case7', row['top_k_case_ids'])
                self.assertNotIn(row['case_id'], row['top_k_case_ids'])
                if row['case_id'] in {'case0','case1'}:
                    self.assertNotIn('case0', row['top_k_case_ids'])
                    self.assertNotIn('case1', row['top_k_case_ids'])

    def test_evaluation_reports_unavailable_without_substitution(self):
        def get_index(mode):
            if mode == 'dinov3_roi':
                raise HTTPException(503, 'model unavailable')
            return {'records':cases(), 'signature':mode, 'failures':[]}
        report = evaluate(get_index)
        self.assertFalse(report['all_modes_available'])
        self.assertEqual(report['models']['dinov3_roi']['status'], 'unavailable')


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patches = [patch.object(main, name, self.root / filename) for name, filename in
                        [('SETTINGS_FILE','settings.json'),('HISTORY_FILE','history.json'),
                         ('ANALYSES_DIR','analyses'),('CASES_FILE','cases.json'),('RESULTS_DIR','results')]]
        for p in self.patches:p.start()
        (self.root / 'results').mkdir()
        self.client = TestClient(main.app)
        stream=BytesIO();Image.new('RGB',(10,10)).save(stream,format='PNG');self.image=stream.getvalue()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_no_detection_null_wear_and_persisted_manual_review(self):
        detection={'detection':None,'detections':[],'annotated_image_url':None}
        with patch.object(main,'detect_tool',return_value=detection), patch.object(main,'encode') as encoder:
            response=self.client.post('/api/analyze',files={'image':('a.png',self.image,'image/png')})
            self.assertEqual(response.status_code,200)
            result=response.json();self.assertIsNone(result['predicted_wear_percent'])
            self.assertEqual(result['status'],'manual_review');encoder.assert_not_called()
            saved=self.client.get('/api/analyses/'+result['analysis_id']).json()
            self.assertEqual(saved['status'],result['status'])
            with patch.object(main.urllib.request,'urlopen') as network:
                answer=self.client.post('/api/assistant',json={'analysis_id':result['analysis_id'],'question':'可以用嗎？'}).json()
                self.assertIn('人工',answer['answer']);network.assert_not_called()

    def test_questions_and_settings_reject_forged_fields(self):
        response=self.client.post('/api/assistant',json={'question':'test','predicted_rate':.1,'analysis_id':'a'*32})
        self.assertEqual(response.status_code,422)
        self.assertEqual(self.client.put('/api/settings',json={'top_k':4}).status_code,422)
        self.assertEqual(self.client.post('/api/analyze',json={'image_url':'x','question':5}).status_code,400)
        self.assertEqual(self.client.post('/api/analyze',json={'image_url':'x','mode':{}}).status_code,400)

    def test_unavailable_model_is_explicit(self):
        detection={'detection':{'bbox':[0,0,10,10],'confidence':.9,'tool_class':'insert'},'detections':[],'annotated_image_url':None}
        with patch.object(main,'detect_tool',return_value=detection),patch.object(main,'encode',side_effect=HTTPException(503,'DINOv3 unavailable')):
            response=self.client.post('/api/analyze',files={'image':('a.png',self.image,'image/png')})
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.client.get('/api/history').json(),[])

    def test_dify_json_contract_and_same_query_case_preparation(self):
        # Resolve the image URL locally using an isolated registered absolute path.
        image_path=self.root / 'query.png';image_path.write_bytes(self.image)
        main.atomic_json(main.CASES_FILE,[{'id':'query','image':str(image_path),'wear_rate':.5}])
        detection={'detection':{'bbox':[1,1,8,8],'confidence':.9,'tool_class':'insert'},'detections':[],'annotated_image_url':None}
        index={'records':cases(),'signature':'test','failures':[]}
        with patch.object(main,'detect_tool',return_value=detection),patch.object(main,'encode',return_value=[1,0]) as encoder,patch.object(main,'current_index',return_value=index):
            result=self.client.post('/api/analyze',json={'image_url':'http://localhost/api/case-image-file/query.jpg','mode':'clip_roi'}).json()
        self.assertEqual(encoder.call_args.args[0].size,(7,7))
        self.assertEqual(result['retrieval']['image_source'],'yolo_roi')
        self.assertEqual(result['retrieval']['actual_k'],5)
        self.assertEqual(result['thresholds']['replace_threshold'],80)
        self.assertEqual(result['weighting'],'exp_cosine_x10')


if __name__ == '__main__':
    unittest.main(verbosity=2)
