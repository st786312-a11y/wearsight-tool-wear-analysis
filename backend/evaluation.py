"""Leave-one-out comparison with identical query AND candidate cohorts."""
from datetime import datetime, timezone
import math
from fastapi import HTTPException
from policy import MODES
from retrieval import WEIGHTING, retrieve


def evaluate(get_index):
    ready, unavailable = {}, {}
    for mode in MODES:
        try:
            ready[mode] = get_index(mode)
        except HTTPException as error:
            unavailable[mode] = {'status': 'unavailable', 'reason': error.detail}
    common = set.intersection(*(set(r['id'] for r in index['records']) for index in ready.values())) if ready else set()
    eligible = set()
    if ready:
        records = [r for r in next(iter(ready.values()))['records'] if r['id'] in common]
        eligible = {q['id'] for q in records if sum(c['fingerprint'] != q['fingerprint'] for c in records) >= 5}
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'protocol': 'leave_one_image_out_common_cohort',
              'weighting': WEIGHTING, 'k': 5, 'units': 'percentage_points',
              'all_modes_available': not unavailable, 'common_candidate_ids': sorted(common),
              'common_query_ids': sorted(eligible), 'models': dict(unavailable),
              'limitations': ['留一影像法未按實體刀具或拍攝批次分組，可能有同刀具資料洩漏；不能視為獨立生產測試。',
                             '不同模型的相似度分布不同；目前共用相似度門檻尚未校準。']}
    for mode, index in ready.items():
        pool = [r for r in index['records'] if r['id'] in common]
        rows = []
        for query in pool:
            if query['id'] not in eligible:
                continue
            result = retrieve(query['embedding'], pool, query['fingerprint'], query['id'], query['file_hash'])
            predicted = result['predicted_wear_percent']
            if predicted is None:
                continue
            actual = query['wear_rate'] * 100
            rows.append({'case_id': query['id'], 'actual_percent': actual, 'predicted_percent': predicted,
                         'absolute_error': abs(actual - predicted),
                         'top1_wear_absolute_difference': abs(actual - result['top_k'][0]['wear_percent']),
                         'wear_std_percent': result['wear_std_percent'], 'average_similarity': result['average_similarity'],
                         'excluded_case_ids': result['excluded_case_ids'],
                         'top_k_case_ids': [c['case_id'] for c in result['top_k']],
                         'self_match_excluded': all(c['case_id'] not in result['excluded_case_ids'] for c in result['top_k'])})
        mean = lambda field: sum(r[field] for r in rows) / len(rows) if rows else None
        report['models'][mode] = {'status': 'evaluated' if rows else 'insufficient_cases', 'sample_count': len(rows),
                                  'mae': mean('absolute_error'),
                                  'rmse': math.sqrt(sum(r['absolute_error'] ** 2 for r in rows) / len(rows)) if rows else None,
                                  'top1_wear_absolute_difference': mean('top1_wear_absolute_difference'),
                                  'top5_wear_std': mean('wear_std_percent'), 'average_similarity': mean('average_similarity'),
                                  'self_match_exclusion_passed': all(r['self_match_excluded'] for r in rows) if rows else None,
                                  'index_signature': index['signature'], 'excluded_index_cases': index['failures'], 'results': rows}
    return report
