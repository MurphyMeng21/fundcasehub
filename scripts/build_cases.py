#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案例库构建脚本（三局证监局）
把 zj-csrc-data 下三局（浙江/北京/上海）的 fund_cases.json 富化成案例库数据，
合并进 cn-law-hub/docs/data/，并派生前端用的 cases.json / cases_full.json。

数据流：
  各局 records.json --filter_fund_cases--> fund_cases.json
          --build_cases.py--> cases_all.json（权威全文，含 severity/tags）
                              ├─ cases.json（轻量，页面列表/检索用）
                              └─ cases_full.json（{case_id: 全文}，懒加载）

用法：
    python3 build_cases.py

注意：
  - 只重建三局证监局记录；中基协(AMAC)、交易所记录原样保留。
  - 证监局行政监管措施的 severity 一律「一般 / 2」（历史 941 条验证一致）。
  - tags 用 CAT_LEVELS 二级分类体系（6 一级 × 26 二级）按关键词匹配。
"""
import json
import re
import os

# ============ 路径 ============
ZJ_BASE = '/Users/yan/Desktop/for_claude/workspace/zj-csrc-data'
OUT_BASE = '/Users/yan/Desktop/for_claude/workspace/cn-law-hub/docs/data'

BUREAUS = ['浙江证监局', '北京证监局', '上海证监局', '深圳证监局', '江苏证监局', '广东证监局', '福建证监局', '四川证监局', '山东证监局', '湖北证监局', '湖南证监局', '厦门证监局', '安徽证监局', '河南证监局', '天津证监局', '重庆证监局', '吉林证监局', '海南证监局', '宁波证监局', '新疆证监局', '陕西证监局', '贵州证监局', '黑龙江证监局', '青岛证监局', '河北证监局', '山西证监局', '广西证监局', '大连证监局', '江西证监局', '辽宁证监局', '西藏证监局', '内蒙古证监局', '甘肃证监局', '云南证监局', '宁夏证监局', '青海证监局']
DATA_DIRS = {
    '浙江证监局': 'zj_csrc_data',
    '北京证监局': 'bj_csrc_data',
    '上海证监局': 'sh_csrc_data',
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
        "勤勉义务": ["勤勉", "审慎", "尽职调查", "投后管理", "未履行", "管理责任", "未有效", "未谨慎"],
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

    与 zj-csrc-data/*_csrc_monitor.py 里的 _strip_metadata 逻辑一致。
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


def fund_case_to_all(fc, agency):
    """一条 fund_cases.json 记录 → cases_all.json 记录。"""
    content = strip_metadata(fc.get('content_text', '') or '')
    # 去尾部噪音（【打印】【关闭窗口】/【字号】/分享到等）
    content = re.sub(r'【打印】\s*【关闭窗口】\s*$', '', content)
    content = re.sub(r'【字号[：:][^】]*】', '', content)
    content = re.sub(r'分享到[：:].*?(?=【字号|$)', '', content, flags=re.DOTALL)
    content = re.sub(r'\n{3,}', '\n\n', content).strip()
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
    }


def main():
    # 1. 加载现有 cases_all.json
    all_path = os.path.join(OUT_BASE, 'cases_all.json')
    with open(all_path, encoding='utf-8') as f:
        all_cases = json.load(f)

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
