# FundCaseHub — 基金处罚案例库

全国 **36 个证监局** + 中基协 + 三大交易所的私募基金相关处罚案例库，共 **3521 条**案例。

线上：https://murphymeng21.github.io/fundcasehub/

## 数据文件（docs/data/）

| 文件 | 内容 |
|------|------|
| `cases.json` | 轻量（结构化字段，列表/详情用） |
| `cases_all.json` | 全量（含正文全文） |
| `cases_full.json` | `{id: 全文}` 映射（详情懒加载） |

## 更新机制

- 数据由 `../zj-csrc-data/update_cases.py` 定期（周度）更新：爬取 36 局新增 → 筛选基金案例 → 集成。
- 构建脚本：`scripts/build_cases.py`（把各局 fund_cases.json 富化成 cases*.json）。

## 说明

- 数据仓库 `fundcasedata`（独立 private 仓库）存 `latest.json` 增量 + `cases_all.json` 全量，供 workbuddy 推 OA / 分析培训用。
