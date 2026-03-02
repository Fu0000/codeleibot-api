#!/usr/bin/env python3
import datetime as dt
import json
import pathlib
import re
from typing import Any, Dict, List

import requests

OUT_ROOT = pathlib.Path('/opt/openclaw/workspace-1/projects/twitter-100k-pet/data/source-scout')


def now_str():
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get(url: str, **kwargs):
    headers = kwargs.pop('headers', {})
    headers.setdefault('User-Agent', 'Mozilla/5.0')
    return requests.get(url, headers=headers, timeout=30, **kwargs)


def scrape_tophub() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        'site': 'tophub.today',
        'url': 'https://tophub.today/',
        'ok': False,
        'channels': [],
        'sample_items': [],
        'notes': [],
    }
    try:
        h = get('https://tophub.today/').text
        channel_pattern = re.compile(r'<a href="(/n/[^"]+)">[\s\S]{0,220}?<div class="zb-kc-Cb">([^<]+)<span>([^<]*)</span>', re.M)
        channels = []
        for m in channel_pattern.finditer(h):
            channels.append({
                'boardPath': m.group(1),
                'platform': m.group(2).strip(),
                'boardName': m.group(3).strip(),
            })
            if len(channels) >= 12:
                break
        out['channels'] = channels

        # sample one board for detailed list
        if channels:
            sample_board = channels[0]['boardPath']
            bh = get(f'https://tophub.today{sample_board}').text
            row_re = re.compile(
                r'<tr>\s*<td align="center">(\d+)\.</td>[\s\S]*?'
                r'<div><a href="([^"]+)"[^>]*>([\s\S]*?)</a></div>\s*'
                r'<div class="item-desc">([\s\S]*?)</div>', re.M)
            items = []
            for m in row_re.finditer(bh):
                title = re.sub(r'<[^>]+>', '', m.group(3)).strip()
                items.append({
                    'rank': int(m.group(1)),
                    'title': title,
                    'heatRaw': re.sub(r'<[^>]+>', '', m.group(4)).strip(),
                    'sourceUrl': m.group(2),
                })
                if len(items) >= 10:
                    break
            out['sample_items'] = items

        out['ok'] = True
        out['notes'].append('可直接抓取HTML；首页拿榜单入口，榜单详情页拿排名/标题/热度。')
    except Exception as e:
        out['notes'].append(f'抓取失败: {e}')
    return out


def scrape_momoyu() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        'site': 'momoyu.cc',
        'url': 'https://momoyu.cc',
        'ok': False,
        'sample_items': [],
        'notes': [],
    }
    try:
        r = get('https://momoyu.cc/api/hot/top')
        j = r.json()
        items = []
        for x in j.get('data', [])[:20]:
            items.append({
                'title': x.get('title'),
                'heatRaw': x.get('extra'),
                'sourceName': x.get('name'),
                'sourceUrl': x.get('link'),
                'id': x.get('id'),
            })
        out['sample_items'] = items
        out['ok'] = True
        out['notes'].append('已找到可直接调用接口: /api/hot/top')
        out['notes'].append('/api/hot/source 需要登录（401），可先用 /api/hot/top 做主源。')
    except Exception as e:
        out['notes'].append(f'抓取失败: {e}')
    return out


def scout_360() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        'site': 'h5.mse.360.cn',
        'url': 'https://h5.mse.360.cn/24thresou.html#/',
        'ok': False,
        'endpoints': [
            'https://api.mse.360.cn/seaword/flow',
            'https://api.mse.360.cn/seaword/catrgory',
        ],
        'notes': [],
    }
    try:
        r = get('https://api.mse.360.cn/seaword/flow', headers={'Referer': 'https://h5.mse.360.cn/24thresou.html#/'})
        out['notes'].append(f'接口返回: {r.text[:120]}')
        out['notes'].append('当前直连返回 errno=1001，推测需动态签名/参数或前端会话。')
        out['notes'].append('建议下一步：浏览器抓包复制真实请求参数后再固化脚本。')
    except Exception as e:
        out['notes'].append(f'探测失败: {e}')
    return out


def scout_attentionvc() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        'site': 'attentionvc.ai',
        'url': 'https://www.attentionvc.ai/article?window=all&lang=zh',
        'ok': False,
        'notes': [],
    }
    try:
        h = get(out['url']).text
        title = re.search(r'<title>(.*?)</title>', h, re.S)
        out['notes'].append(f'页面可访问，标题: {(title.group(1).strip() if title else "N/A")}')
        out['notes'].append('该页内容主要由前端动态渲染，直接HTML无可用榜单数据。')
        out['notes'].append('建议浏览器模式抓 Network（XHR/fetch）获取真实文章榜单接口。')
    except Exception as e:
        out['notes'].append(f'探测失败: {e}')
    return out


def main():
    ts = now_str()
    day = dt.datetime.now().strftime('%Y-%m-%d')
    out_dir = OUT_ROOT / day
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        'generatedAt': ts,
        'records': [
            scrape_tophub(),
            scrape_momoyu(),
            scout_360(),
            scout_attentionvc(),
        ],
        'schemaSuggestion': {
            'fields': ['site', 'title', 'rank', 'heatRaw', 'heatNorm', 'category', 'publishTime', 'sourceUrl', 'crawlTime', 'confirmed'],
            'csvHeader': 'site,title,rank,heat_raw,heat_norm,category,publish_time,source_url,crawl_time,confirmed'
        }
    }

    jpath = out_dir / 'scout_report.json'
    jpath.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    lines: List[str] = []
    lines.append(f'# Source Scout Report ({ts})')
    for r in report['records']:
        lines.append(f"\n## {r['site']}\n")
        lines.append(f"- URL: {r['url']}")
        lines.append(f"- OK: {r['ok']}")
        if r.get('channels'):
            lines.append('- 频道样例:')
            for c in r['channels'][:6]:
                lines.append(f"  - {c['platform']} {c['boardName']} ({c['boardPath']})")
        if r.get('sample_items'):
            lines.append('- 数据样例:')
            for x in r['sample_items'][:5]:
                lines.append(f"  - {x.get('title','')[:50]} | {x.get('heatRaw','')} | {x.get('sourceUrl','')}")
        if r.get('endpoints'):
            lines.append('- 候选接口:')
            for ep in r['endpoints']:
                lines.append(f'  - {ep}')
        if r.get('notes'):
            lines.append('- 备注:')
            for n in r['notes']:
                lines.append(f'  - {n}')

    mpath = out_dir / 'scout_report.md'
    mpath.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(json.dumps({'ok': True, 'json': str(jpath), 'markdown': str(mpath)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
