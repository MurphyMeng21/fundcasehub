# -*- coding: utf-8 -*-
"""校验 build_cases 的 classify_tags / strip_metadata 是否与历史数据一致。"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_cases import classify_tags, strip_metadata, BUREAUS

OUT = '/Users/yan/Desktop/for_claude/workspace/cn-law-hub/docs/data'
ZJ = '/Users/yan/Desktop/for_claude/workspace/zj-csrc-data'

ca = json.load(open(os.path.join(OUT, 'cases_all.json'), encoding='utf-8'))
zs = [x for x in ca if x.get('agency') in BUREAUS]
print('证监局记录数:', len(zs))

# 校验1: classify_tags 重现率
tag_match = 0
tag_diff = 0
for x in zs:
    recomputed = classify_tags(x.get('content_text', ''), ' '.join(x.get('violations', [])))
    if set(recomputed) == set(x.get('tags', [])):
        tag_match += 1
    else:
        tag_diff += 1
        if tag_diff <= 5:
            print('  标签差异:', x['party'][:20], '| 历史:', x.get('tags'), '| 重算:', recomputed)
print(f'classify_tags 重现率: {tag_match}/{len(zs)} (差异 {tag_diff})')

# 校验2: strip_metadata 重现率
fc = json.load(open(os.path.join(ZJ, 'zj_csrc_data', 'fund_cases.json'), encoding='utf-8'))
by_party = {x['party']: x for x in fc}
strip_match = 0
strip_diff = 0
checked = 0
for x in zs:
    if x['party'] in by_party and by_party[x['party']].get('content_text'):
        checked += 1
        stripped = strip_metadata(by_party[x['party']]['content_text'])
        if stripped == x.get('content_text', ''):
            strip_match += 1
        else:
            strip_diff += 1
            if strip_diff <= 3:
                print('  正文差异:', x['party'][:20], '| 历史', len(x.get('content_text', '')), '重算', len(stripped))
print(f'strip_metadata 重现率: {strip_match}/{checked} (差异 {strip_diff})')
