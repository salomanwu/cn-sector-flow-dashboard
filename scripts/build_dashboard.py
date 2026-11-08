# -*- coding: utf-8 -*-
"""抓取 A 股资金流，生成自包含静态看板 docs/index.html"""
import os
import html
from datetime import datetime, timezone, timedelta

import pandas as pd
import akshare as ak

OUT = "docs/index.html"


def fetch(fn, label):
    """单个数据源失败不影响整页生成"""
    try:
        return fn(), label, None
    except Exception as e:
        return None, label, f"{type(e).__name__}: {e}"


def pick(df, *keywords):
    """按关键字模糊找列名，兼容 AKShare 不同版本"""
    for kw in keywords:
        for c in df.columns:
            if kw in str(c):
                return c
    return None


def rows(df, name_keys, value_keys, extra_keys=()):
    """抽成 [(名称, 净额亿元, 备注), ...]"""
    n = pick(df, *name_keys)
    v = pick(df, *value_keys)
    if n is None or v is None or df.empty:
        return []
    ex = [(k, pick(df, *k)) for k in extra_keys]
    out = []
    for _, r in df.iterrows():
        try:
            val = float(r[v]) / 1e8
        except (TypeError, ValueError):
            continue
        note = ""
        if ex:
            bits = []
            for _, c in ex:
                if c is not None and not pd.isna(r[c]):
                    bits.append(f"{r[c]}")
            note = " · ".join(bits[:2])
        out.append((str(r[n]), val, note))
    return out


def bar(name, val, note, scale):
    color = "#d64545" if val >= 0 else "#2e9e6b"   # 红=流入 绿=流出
    w = min(100, abs(val) / scale * 100) if scale else 0
    sign = "+" if val >= 0 else ""
    return f"""<div class="row">
      <div class="meta"><span class="nm">{html.escape(name)}</span>
        <span class="val" style="color:{color}">{sign}{val:.2f}亿</span></div>
      <div class="track"><div class="fill" style="width:{w:.1f}%;background:{color}"></div></div>
      <div class="note">{html.escape(note)}</div>
    </div>"""


def section(title, data, top=10):
    if not data:
        return f'<section><h2>{html.escape(title)}</h2><p class="empty">本次未取到数据</p></section>'
    s = sorted(data, key=lambda x: x[1], reverse=True)
    inflow, outflow = s[:top], list(reversed(s[-top:]))
    scale = max((abs(v) for _, v, _ in s), default=1) or 1
    a = "".join(bar(n, v, note, scale) for n, v, note in inflow)
    b = "".join(bar(n, v, note, scale) for n, v, note in outflow)
    return f"""<section>
      <h2>{html.escape(title)}</h2>
      <h3>净流入 TOP{len(inflow)}</h3>{a}
      <h3>净流出 TOP{len(outflow)}</h3>{b}
    </section>"""


def main():
    jobs = [
        ("行业资金流 · 今日", lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")),
        ("行业资金流 · 5日",  lambda: ak.stock_sector_fund_flow_rank(indicator="5日",  sector_type="行业资金流")),
        ("行业资金流 · 10日", lambda: ak.stock_sector_fund_flow_rank(indicator="10日", sector_type="行业资金流")),
        ("概念资金流 · 今日", lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")),
        ("个股主力净流入",   lambda: ak.stock_individual_fund_flow_rank(indicator="今日")),
    ]

    sections, errors = [], []
    for title, fn in jobs:
        df, label, err = fetch(fn, title)
        if err:
            errors.append(f"{label} → {err}")
            sections.append(section(title, []))
            continue
        if "个股" in title:
            data = rows(df, ("名称", "股票简称"), ("主力净流入-净额", "主力净流入"),
                        ("最新价", "今日涨跌幅"))
        else:
            data = rows(df, ("名称", "板块名称"), ("主力净流入-净额", "主力净流入"),
                        ("涨跌幅",))
        sections.append(section(title, data))

    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    err_html = ""
    if errors:
        err_html = "<div class='warn'><b>部分数据源未取到：</b><br>" + \
                   "<br>".join(html.escape(e) for e in errors) + "</div>"

    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A股资金流盘后看板</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#0f1218;color:#e8ebf0;font:15px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:820px;margin:0 auto;padding:20px 16px 60px}}
header h1{{font-size:22px;margin:0 0 6px}}
.sub{{color:#8b95a5;font-size:13px}}
section{{margin-top:28px;background:#171c25;border:1px solid #242c38;border-radius:12px;padding:16px}}
h2{{font-size:17px;margin:0 0 12px}} h3{{font-size:13px;color:#8b95a5;margin:16px 0 8px;font-weight:500}}
.row{{margin-bottom:11px}}
.meta{{display:flex;justify-content:space-between;gap:10px;font-size:14px}}
.nm{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.val{{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}}
.track{{height:7px;background:#222a36;border-radius:4px;margin-top:4px;overflow:hidden}}
.fill{{height:100%;border-radius:4px}}
.note{{font-size:11px;color:#6e7889;margin-top:2px}}
.empty,.warn{{font-size:13px;color:#9aa3b2}}
.warn{{margin-top:20px;padding:12px;background:#2a2318;border:1px solid #4a3a20;border-radius:8px;line-height:1.8}}
footer{{margin-top:30px;font-size:12px;color:#6e7889;line-height:1.8}}
</style></head><body><div class="wrap">
<header><h1>A股资金流 · 盘后看板</h1>
<div class="sub">数据时间 {now}（北京时间） · 每交易日 18:17 自动更新 · 主力净额，单位亿元</div></header>
{err_html}
{"".join(sections)}
<footer>数据源：AKShare（东方财富公开接口）。「主力净流入」按成交单笔金额分档推算，为估算值而非交易所逐笔数据，各平台口径可能不一致。<br>仅供复盘参考，不构成投资建议。</footer>
</div></body></html>"""

    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"written {OUT}, errors={len(errors)}")


if __name__ == "__main__":
    main()
