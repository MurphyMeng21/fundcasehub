#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案例库构建脚本（36 证监局 + 中基协 AMAC）
把 fundcase-crawler 下 36 局的 fund_cases.json 与 amac_data/records.json（中基协纪律处分）
富化成案例库数据，合并进 fundcasehub/docs/data/，并派生前端用的 cases.json / cases_full.json。

数据流：
  各局 records.json --filter_fund_cases--> fund_cases.json ┐
  amac_data/records.json（crawl_amac_cases.py 产出）      ┴─build_cases.py--> cases_all.json
                              ├─ cases.json（轻量，页面列表/检索用）
                              └─ cases_full.json（{case_id: 全文}，懒加载）

用法：
    python3 build_cases.py

注意：
  - 证监局记录按 source_url 去重后追加；中基协(AMAC)记录按 source_url(=pdf_url) 去重后追加，
    交易所记录原样保留。
  - 证监局行政监管措施的 severity 一律「一般 / 2」（历史验证一致）；
    中基协 severity 按处分力度映射（见 AMAC_SEVERITY_RULES，从存量 357 条反推）。
  - tags 用 CAT_LEVELS 二级分类体系（6 一级 × 26 二级）按关键词匹配；
    business_stage 复用 fundcase-crawler/tag_business_stage.py 的 tag_stages。
"""
import json
import os
import re
import sys

# ============ 路径（相对脚本位置，避免硬编码父目录名）============
HERE = os.path.dirname(os.path.abspath(__file__))  # fundcasehub/scripts/
ZJ_BASE = os.path.join(HERE, '..', '..', 'fundcase-crawler')
OUT_BASE = os.path.join(HERE, '..', 'docs', 'data')
sys.path.insert(0, ZJ_BASE)
from tag_business_stage import tag_stages  # noqa: E402

AMAC_RECORDS = os.path.join(ZJ_BASE, 'amac_data', 'records.json')
AMAC_AGENCY = '中国证券投资基金业协会（中基协）'

BUREAUS = ['浙江证监局', '北京证监局', '上海证监局', '深圳证监局', '江苏证监局', '广东证监局', '福建证监局', '四川证监局', '山东证监局', '湖北证监局', '湖南证监局', '厦门证监局', '安徽证监局', '河南证监局', '天津证监局', '重庆证监局', '吉林证监局', '海南证监局', '宁波证监局', '新疆证监局', '陕西证监局', '贵州证监局', '黑龙江证监局', '青岛证监局', '河北证监局', '山西证监局', '广西证监局', '大连证监局', '江西证监局', '辽宁证监局', '西藏证监局', '内蒙古证监局', '甘肃证监局', '云南证监局', '宁夏证监局', '青海证监局']
DATA_DIRS = {
    '浙江证监局': 'zhejiang_csrc_data',
    '北京证监局': 'beijing_csrc_data',
    '上海证监局': 'shanghai_csrc_data',
    '深圳证监局': 'shenzhen_csrc_data',
    '江苏证监局': 'jiangsu_csrc_data',
    '广东证监局': 'guangdong_csrc_data',
    '福建证监局': 'fujian_csrc_data',
    '四川证监局': 'sichuan_csrc_data',
    '山东证监局': 'shandong_csrc_data',
    '湖北证监局': 'hubei_csrc_data',
    '湖南证监局': 'hunan_csrc_data',
    '厦门证监局': 'xiamen_csrc_data',
    '安徽证监局': 'anhui_csrc_data',
    '河南证监局': 'henan_csrc_data',
    '天津证监局': 'tianjin_csrc_data',
    '重庆证监局': 'chongqing_csrc_data',
    '吉林证监局': 'jilin_csrc_data',
    '海南证监局': 'hainan_csrc_data',
    '宁波证监局': 'ningbo_csrc_data',
    '新疆证监局': 'xinjiang_csrc_data',
    '陕西证监局': 'shaanxi_csrc_data',
    '贵州证监局': 'guizhou_csrc_data',
    '黑龙江证监局': 'heilongjiang_csrc_data',
    '青岛证监局': 'qingdao_csrc_data',
    '河北证监局': 'hebei_csrc_data',
    '山西证监局': 'shanxi_csrc_data',
    '广西证监局': 'guangxi_csrc_data',
    '大连证监局': 'dalian_csrc_data',
    '江西证监局': 'jiangxi_csrc_data',
    '辽宁证监局': 'liaoning_csrc_data',
    '西藏证监局': 'xizang_csrc_data',
    '内蒙古证监局': 'neimenggu_csrc_data',
    '甘肃证监局': 'gansu_csrc_data',
    '云南证监局': 'yunnan_csrc_data',
    '宁夏证监局': 'ningxia_csrc_data',
    '青海证监局': 'qinghai_csrc_data',
}

# ============ 二级分类体系（6 一级 × 26 二级）============
CAT_LEVELS = {
    "公司治理与登记备案": {
        "登记备案": ["备案", "登记", "未登记", "未备案", "未办理", "登记信息不"],
        "内控合规": ["内控制度", "内部控制", "内控", "合规制度", "制度不健全"],
        "人员场所": ["从业人员", "办公场所", "高管", "合规风控负责人", "人员配备", "部门设置", "人员不足", "无独立办公", "未设合规"],
        "虚假材料": ["虚假", "伪造", "篡改", "不实", "造假"],
        "信息报送": ["信息更新", "未及时更新", "未变更", "未报送", "未报告", "未向协会报告"],
        "不配合监管": ["不配合", "拒绝配合", "妨碍", "阻挠", "拒绝提供"],
        "违规减持": ["减持", "一致行动", "举牌"],
    },
    "募集销售与投资者适当性": {
        "合格投资者": ["合格投资者", "投资者人数", "投资者适当性", "穿透核查", "拼凑"],
        "销售违规": ["销售", "委托推介", "非本机构", "基金销售", "无销售资格", "募集"],
        "承诺收益": ["保本", "承诺收益", "预期收益", "固定收益", "最低收益", "保底"],
        "公开宣传": ["公开宣传", "公开推介", "向不特定对象", "互联网宣传", "微信平台", "公众号推广"],
        "非法集资": ["汇集资金", "非法集资", "非法吸收"],
    },
    "产品运作与合同一致性": {
        "勤勉义务": ["勤勉", "审慎", "尽职调查", "投后管理", "未履行", "未切实履行", "管理责任", "未有效", "未谨慎", "主动管理职责"],
        "信息披露": ["信息披露", "未披露", "未及时披露", "未按规定披露", "披露不"],
        "关联交易": ["关联交易", "利益输送", "自融", "关联方", "利益冲突"],
        "挪用侵占": ["挪用", "侵占", "基金财产", "基金资产"],
        "投资运作违规": ["投资范围", "未按合同", "未按约定", "超越合同", "违规投资", "超比例"],
        "估值违规": ["估值", "净值", "公允价值", "估值方法"],
        "期货与资管业务": ["通道业务", "场外期权", "收益互换", "变相融资", "杠杆融资",
                       "期货公司监督", "期货资管", "资产管理计划.*违规", "资管计划.*违规"],
        "风险指标违规": ["集中度.*超标", "总资产占净资产.*超", "杠杆.*超标",
                       "风险指标", "止损线", "预警线"],
        "资金池混同": ["资金池", "混同运作", "单独管理", "单独建账", "独立核算", "不公平对待"],
        "募新还旧": ["募新还旧", "借新还旧"],
    },
    "程序化交易与算法管理": {
        "程序化交易管理": ["程序化", "量化", "高频", "算法", "交易系统", "报告管理", "程序化交易"],
    },
    "异常交易与市场操纵": {
        "异常交易行为": ["异常交易", "自成交", "报撤单", "拉抬", "打压", "对倒", "虚假申报"],
        "市场操纵内幕交易": ["操纵", "内幕交易", "利用未公开信息", "老鼠仓", "股价操纵"],
    },
    "网下打新": {
        "网下打新违规": ["打新", "网下申购", "网下配售", "新股", "IPO"],
    },
}


def classify_tags(text, violations_text=""):
    """返回 ['一级/二级', ...] 标签列表。关键词按正则匹配（部分词条含 .* 模式）。"""
    combined = (text or '')[:8000] + ' ' + (violations_text or '')
    tags = set()
    for l1, subs in CAT_LEVELS.items():
        for l2, keywords in subs.items():
            for kw in keywords:
                if re.search(kw, combined):
                    tags.add(f"{l1}/{l2}")
                    break
    return sorted(tags)


def strip_metadata(text):
    """剥离证监局详情页正文里的元数据区（索引号/分类/发布机构/发文日期/名称/文号/主题词）。

    与 fundcase-crawler/*_csrc_monitor.py 里的 _strip_metadata 逻辑一致。
    """
    if not text:
        return ''
    # 方式1: 找"主题词"后的值，从下一行截取
    m = re.search(r'主\s*题\s*词\s*\n([^\n]*)\n', text)
    if m:
        stripped = text[m.end():].strip()
        if len(stripped) > 20:
            return stripped
    # 方式2: 找第一个"XXX:"行（当事人+冒号），跳过元数据字段
    meta_keywords = ['索引号', '分类', '发布机构', '发文日期', '名称', '文号',
                     '主题词', 'bm56000001', '中国证券', '浙江证监局']
    lines = text.split('\n')
    for i, line in enumerate(lines):
        ls = line.strip()
        if not ls:
            continue
        if any(kw in ls for kw in meta_keywords):
            continue
        if re.match(r'^.{2,40}[：:]', ls) and not re.match(r'^\d{10,}', ls):
            return '\n'.join(lines[i:]).strip()
    return text


def format_csrc_content(text):
    """证监局正文排版：碎片重排（合并碎行/单独成行的数字）+ 逻辑段落分层。"""
    if not text:
        return text
    # 1. 日期碎片合并（"2026\n年\n9\n月\n15\n日" → "2026年9月15日"）
    text = re.sub(r'(\d{4})\n年\n(\d{1,2})\n月\n(\d{1,2})\n日', r'\1年\2月\3日', text)
    # 2. 合并单独成行的数字（"之日起\n7\n日内" → "之日起7日内"）
    text = re.sub(r'(?<=[一-龥])\n(\d{1,3})\n(?=[一-龥])', r'\1', text)
    # 2. 碎片行合并：非逻辑段落边界、非列举项的行，合并到前一行
    boundary_prefixes = ('经查', '我局', '上述行为', '你作为', '你应当', '如果对本', '根据', '你公司应')
    lines = text.split('\n')
    paras = []
    for line in lines:
        ls = line.strip()
        if not ls:
            continue
        is_para = (
            ls.endswith('：') or ls.endswith(':') or
            any(ls.startswith(p) for p in boundary_prefixes) or
            re.match(r'^[一-龥]{2,8}证监局$', ls) or
            re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', ls)
        )
        is_list_item = re.match(r'^[一二三四五六七八九十]+、', ls)
        if is_para or not paras:
            paras.append(ls)
        elif is_list_item:
            paras[-1] += '\n' + ls
        else:
            paras[-1] += ls
    text = '\n\n'.join(paras).strip()
    # 3. 落款处理
    #    a. 拆开连在一起的「证监局日期」
    text = re.sub(r'(证监局)(\d{4}年\d{1,2}月\d{1,2}日)', r'\1\n\2', text)
    #    b. 空行分隔的「证监局\n\n日期」→ 单换行
    text = re.sub(r'(证监局)\n\n(\d{4}年\d{1,2}月\d{1,2}日)', r'\1\n\2', text)
    #    c. 落款独立成段：正文（句号/分号结尾）与落款之间加空行
    text = re.sub(r'([。；])([一-龥]{2,8}证监局\n\d{4}年\d{1,2}月\d{1,2}日)', r'\1\n\n\2', text)
    return text


def format_amac_content(text):
    """中基协 OCR 正文：去中文间空格 + 按章节标记分段。"""
    if not text:
        return text
    # 去中文相邻字之间的空格（OCR 把 PDF 行尾换行转成空格）
    text = re.sub(r'(?<=[一-龥])\s+(?=[一-龥])', '', text)
    # 按章节标记分段（marker 前非换行时才加空行，幂等）
    for marker in ['一、基本事实', '二、申辩意见', '三、审理意见']:
        text = re.sub(r'(?<!\n)' + marker, '\n\n' + marker, text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fund_case_to_all(fc, agency):
    """一条 fund_cases.json 记录 → cases_all.json 记录。"""
    content = strip_metadata(fc.get('content_text', '') or '')
    # 去尾部噪音（【打印】【关闭窗口】/【字号】/分享到等）
    content = re.sub(r'【打印】\s*【关闭窗口】\s*$', '', content)
    content = re.sub(r'【字号[：:][^】]*】', '', content)
    content = re.sub(r'分享到[：:].*?(?=【字号|$)', '', content, flags=re.DOTALL)
    content = re.sub(r'\n{3,}', '\n\n', content).strip()
    content = format_csrc_content(content)
    violations = fc.get('violations', []) or []
    tags = classify_tags(content, ' '.join(violations))
    return {
        'party': fc.get('party', ''),
        'party_type': fc.get('party_type', ''),
        'position': '',
        'agency': agency,
        'date': fc.get('date', ''),
        'case_no': fc.get('case_no', ''),
        'penalty': fc.get('penalty', ''),
        'severity': '一般',
        'severity_score': 2,
        'tags': tags,
        'categories': sorted(set(t.split('/')[0] for t in tags)),
        'violations': violations,
        'defense': [],
        'laws': fc.get('laws', []),
        'content_preview': content[:3000],
        'content_text': content,
        'source': agency,
        'source_url': fc.get('detail_url', ''),
        'penalty_type': fc.get('penalty_type', '监管措施'),
        'business_stage': tag_stages(tags, violations),
        'added_date': fc.get('date', ''),
    }


# ============ 中基协（AMAC）纪律处分 ============
# 处分力度 → severity 映射（从存量 357 条反推，2026-10-23 校准：可判定条目吻合率 ~88%）。
# 按「力度降序、先命中先用」；存量口径：撤销登记/暂停受理产品备案=严重，公开谴责/黑名单=较重，警告=一般。
# 未命中（penalty 为空或 OCR 噪音）默认「较重」，提示人工关注。
AMAC_SEVERITY_RULES = [
    (4, '严重', ['撤销', '暂停受理', '暂停办理']),
    (3, '较重', ['黑名单', '谴责', '公开批评', '暂停']),
    (2, '一般', ['警告', '警示', '责令', '限期改正', '通报批评', '内部惩戒']),
]


def amac_severity(penalty_text):
    """按处分措施文本映射 severity，返回 (score, 名称)。未命中 → (3, 较重)。"""
    p = penalty_text or ''
    for score, name, keywords in AMAC_SEVERITY_RULES:
        if any(kw in p for kw in keywords):
            return score, name
    return 3, '较重'


def amac_record_to_all(rec):
    """一条 amac_data/records.json 记录 → cases_all.json 记录（中基协纪律处分）。"""
    f = rec.get('fields', {}) or {}
    content = format_amac_content(rec.get('ocr_text', '') or '')
    violations = f.get('violations', []) or []
    tags = classify_tags(content, ' '.join(violations))
    sev_score, sev_name = amac_severity(f.get('penalty', ''))
    date = rec.get('date', '') or f.get('date', '')
    return {
        'party': f.get('party', '') or rec.get('name', ''),
        'party_type': '自然人' if rec.get('channel') == 'scfry' else '机构',
        'position': '',
        'agency': AMAC_AGENCY,
        'date': date,
        'case_no': f.get('case_no', ''),
        'penalty': f.get('penalty', ''),
        'severity': sev_name,
        'severity_score': sev_score,
        'tags': tags,
        'categories': sorted(set(t.split('/')[0] for t in tags)),
        'violations': violations,
        'defense': f.get('defense', []) or [],
        'laws': f.get('laws', []) or [],
        'content_preview': content[:3000],
        'content_text': content,
        'source': '中基协',
        'source_url': rec.get('pdf_url', ''),
        'penalty_type': '纪律处分',
        'business_stage': tag_stages(tags, violations),
        'added_date': date,
    }


def main():
    # 1. 加载现有 cases_all.json
    all_path = os.path.join(OUT_BASE, 'cases_all.json')
    with open(all_path, encoding='utf-8') as f:
        all_cases = json.load(f)

    # 1.5 统一当事人类型：'人员'（中基协受处分人员）→ '自然人'
    for x in all_cases:
        if x.get('party_type') == '人员':
            x['party_type'] = '自然人'

    # 1.6 中基协 OCR 正文排版：去空格 + 按章节分段
    for x in all_cases:
        if '中基协' in x.get('agency', ''):
            ct = format_amac_content(x.get('content_text', '') or '')
            x['content_text'] = ct
            x['content_preview'] = ct[:3000]
            # 存量口径修正：中基协做出的是「纪律处分」，不是证监局的「监管措施」（2026-10-23）
            if x.get('penalty_type') != '纪律处分':
                x['penalty_type'] = '纪律处分'

    # 1.7 证监局正文段落分层（对保留的历史数据也处理）
    for x in all_cases:
        if '证监局' in x.get('agency', ''):
            ct = format_csrc_content(x.get('content_text', '') or '')
            x['content_text'] = ct
            x['content_preview'] = ct[:3000]

    # 已有记录的去重键（source_url = detail_url）
    existing_urls = {x.get('source_url', '') for x in all_cases}

    # 2. 只追加"新增"的三局记录（保留历史记录原样，避免改动其正文清洗/标签）
    added = 0
    for agency in BUREAUS:
        fc_path = os.path.join(ZJ_BASE, DATA_DIRS[agency], 'fund_cases.json')
        with open(fc_path, encoding='utf-8') as f:
            fund_cases = json.load(f)
        new_count = 0
        for fc in fund_cases:
            if fc.get('detail_url', '') in existing_urls:
                continue
            all_cases.append(fund_case_to_all(fc, agency))
            existing_urls.add(fc.get('detail_url', ''))
            new_count += 1
            added += 1
        print(f'{agency}: 新增 {new_count} 条')

    # 2.5 中基协（AMAC）纪律处分：按 source_url(=pdf_url) 去重后追加
    #     未 OCR 的记录（无 ocr_text）跳过，等 crawl_amac_cases.py 补齐后下次自动入库
    if os.path.exists(AMAC_RECORDS):
        with open(AMAC_RECORDS, encoding='utf-8') as f:
            amac_records = json.load(f)
        amac_new = 0
        amac_skip_noocr = 0
        for rec in amac_records:
            if rec.get('source_url', rec.get('pdf_url', '')) in existing_urls:
                continue
            if not rec.get('ocr_text'):
                amac_skip_noocr += 1
                continue
            all_cases.append(amac_record_to_all(rec))
            existing_urls.add(rec.get('source_url', rec.get('pdf_url', '')))
            amac_new += 1
            added += 1
        print(f'中基协（AMAC）: 新增 {amac_new} 条' +
              (f'（另有 {amac_skip_noocr} 条待 OCR，暂不入库）' if amac_skip_noocr else ''))
    else:
        print(f'中基协（AMAC）: 未找到 {AMAC_RECORDS}，跳过')

    # 3. 按决定日期倒序
    all_cases.sort(key=lambda x: x.get('date', '') or '', reverse=True)

    # 4. 写 cases_all.json
    with open(all_path, 'w', encoding='utf-8') as f:
        json.dump(all_cases, f, ensure_ascii=False, indent=2)

    # 5. 派生 cases.json（轻量）+ cases_full.json（全文 map）
    light = []
    full = {}
    for i, c in enumerate(all_cases):
        cid = f"case-{c['source'].replace(' ', '-')}-{i}"
        light.append({
            'id': cid,
            'party': c['party'],
            'party_type': c.get('party_type', ''),
            'position': c.get('position', ''),
            'agency': c['agency'],
            'date': c['date'],
            'case_no': c.get('case_no', ''),
            'penalty': c['penalty'],
            'severity': c['severity'],
            'severity_score': c.get('severity_score', 2),
            'tags': c.get('tags', []),
            'categories': c.get('categories', []),
            'violations': c.get('violations', []),
            'defense': c.get('defense', []),
            'laws': c.get('laws', [])[:20],
            'content_preview': c.get('content_preview', ''),
            'source': c['source'],
            'source_url': c.get('source_url', ''),
            'penalty_type': c.get('penalty_type', '监管措施'),
            'business_stage': c.get('business_stage', ''),
            'added_date': c.get('added_date', c.get('date', '')),
        })
        full[cid] = c.get('content_text', '')

    with open(os.path.join(OUT_BASE, 'cases.json'), 'w', encoding='utf-8') as f:
        json.dump(light, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_BASE, 'cases_full.json'), 'w', encoding='utf-8') as f:
        json.dump(full, f, ensure_ascii=False, indent=2)

    print(f'\n完成：总案例 {len(all_cases)} 条（本次新增 {added} 条）')
    print(f'  cases_all.json / cases.json / cases_full.json 已更新')


if __name__ == '__main__':
    main()
