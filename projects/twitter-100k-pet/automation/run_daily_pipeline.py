#!/usr/bin/env python3
import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import re
import time
import traceback
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

ROOT = pathlib.Path('/opt/openclaw/workspace-1/projects/twitter-100k-pet')
DATA_DIR = ROOT / 'data' / 'hotspots'
RAW_DIR = DATA_DIR / 'raw'
ANALYSIS_DIR = DATA_DIR / 'analysis'
DAILY_DIR = DATA_DIR / 'daily'
QUEUE_DIR = ROOT / 'CONTENT_QUEUE'
IMG_DIR = ROOT / 'generated-comics'

GROK_BASE = os.environ.get('GROK_BASE_URL', 'https://cap-grok.chuhaibox.com/v1')
GROK_MODEL = os.environ.get('GROK_ANALYSIS_MODEL', 'grok-3-mini')
GOOGLE_KEY = os.environ.get('GOOGLE_API_KEY', '')
GOOGLE_TEXT_MODEL = os.environ.get('GOOGLE_TEXT_MODEL', 'gemini-3.1-flash')
GOOGLE_IMAGE_MODEL = os.environ.get('GOOGLE_IMAGE_MODEL', 'gemini-3.1-flash-image-preview')

DEFAULT_SOURCES = [
    {"name": "Google News World", "url": "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"},
    {"name": "Google News Tech", "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"},
]


def now_parts():
    now = dt.datetime.now()
    day = now.strftime('%Y-%m-%d')
    hour = now.strftime('%H')
    stamp = now.strftime('%Y-%m-%d %H:%M:%S')
    return now, day, hour, stamp


def ensure_dirs(day: str):
    for d in [RAW_DIR / day, ANALYSIS_DIR / day, DAILY_DIR, QUEUE_DIR, IMG_DIR / day / 'auto']:
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    p = ROOT / 'automation' / 'config.local.json'
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {"sources": DEFAULT_SOURCES}


def fetch_rss(url: str, timeout=20) -> List[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        xml = resp.read()
    root = ET.fromstring(xml)
    items = []
    for item in root.findall('.//item')[:20]:
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        pub = (item.findtext('pubDate') or '').strip()
        desc = (item.findtext('description') or '').strip()
        if title and link:
            items.append({
                'title': title,
                'url': link,
                'summary': re.sub('<[^>]+>', '', desc)[:220],
                'publishedAt': pub,
            })
    return items


def load_manual_topics() -> List[Dict[str, Any]]:
    p = DATA_DIR / 'inbox' / 'manual_topics.jsonl'
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def analyze_with_grok(topic: Dict[str, Any], retries=3) -> Optional[Dict[str, Any]]:
    prompt = f"""
你是内容策略分析师。根据输入热点，输出严格JSON：
{{
  "category":"爆笑|警示|教育|引人深思|创造力|感人故事",
  "emotionScore":0-100,
  "riskLevel":"low|medium|high",
  "angleSuggestions":["角度1","角度2"],
  "comicIdea":"两格漫画剧情",
  "caption":"可发推文案"
}}

输入：
标题：{topic.get('title','')}
摘要：{topic.get('summary','')}
""".strip()

    payload = {
        'model': GROK_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
        # 关键：该服务 stream=true 容易触发 401，固定关闭流式
        'stream': False,
    }

    for i in range(1, retries + 1):
        try:
            r = requests.post(f'{GROK_BASE}/chat/completions', json=payload, timeout=45)
            txt = r.text
            if 'event: error' in txt or 'AppChatReverse' in txt:
                time.sleep(0.8 * i)
                continue
            j = r.json()
            content = j['choices'][0]['message']['content']
            m = re.search(r'\{[\s\S]*\}', content)
            if not m:
                time.sleep(0.6 * i)
                continue
            return json.loads(m.group(0))
        except Exception:
            time.sleep(0.8 * i)
            continue
    return None


def analyze_with_google(topic: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not GOOGLE_KEY:
        return None
    prompt = f"""
你是内容策略分析师。根据输入热点，输出严格JSON：
{{
  "category":"爆笑|警示|教育|引人深思|创造力|感人故事",
  "emotionScore":0-100,
  "riskLevel":"low|medium|high",
  "angleSuggestions":["角度1","角度2"],
  "comicIdea":"两格漫画剧情",
  "caption":"可发推文案"
}}

输入：
标题：{topic.get('title','')}
摘要：{topic.get('summary','')}
""".strip()

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GOOGLE_TEXT_MODEL}:generateContent?key={GOOGLE_KEY}'
    payload = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=45)
        if r.status_code != 200:
            return None
        j = r.json()
        txt = j['candidates'][0]['content']['parts'][0]['text']
        m = re.search(r'\{[\s\S]*\}', txt)
        if not m:
            return None
        return json.loads(m.group(0))
    except Exception:
        return None


def gen_image_google(title: str, idea: str, out_path: pathlib.Path) -> bool:
    if not GOOGLE_KEY:
        return False
    prompt = f"""
请生成一张两格漫画（上下结构），原创角色，粗糙蜡笔手绘风，非3D。
中文文字清晰可读，无乱码。
主题：{title}
剧情：{idea}
要求：第一格铺垫，第二格反转，适合社媒传播。
""".strip()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GOOGLE_IMAGE_MODEL}:generateContent?key={GOOGLE_KEY}'
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']},
    }
    try:
        r = requests.post(url, json=payload, timeout=90)
        if r.status_code != 200:
            return False
        parts = r.json().get('candidates', [{}])[0].get('content', {}).get('parts', [])
        for p in parts:
            if 'inlineData' in p:
                out_path.write_bytes(base64.b64decode(p['inlineData']['data']))
                return True
        return False
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['quick', 'deep'], default='quick')
    ap.add_argument('--limit', type=int, default=6)
    args = ap.parse_args()

    now, day, hour, stamp = now_parts()
    ensure_dirs(day)
    cfg = load_config()

    topics = []
    for s in cfg.get('sources', DEFAULT_SOURCES):
        try:
            items = fetch_rss(s['url'])
            for it in items:
                it['source'] = s['name']
            topics.extend(items)
        except Exception:
            continue
    topics.extend(load_manual_topics())

    # dedupe by title
    seen = set()
    uniq = []
    for t in topics:
        key = (t.get('title') or '').strip()
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(t)
    topics = uniq[: max(args.limit, 3)]

    raw_path = RAW_DIR / day / f'{hour}.json'
    raw_path.write_text(json.dumps({'timestamp': stamp, 'mode': args.mode, 'topics': topics}, ensure_ascii=False, indent=2), encoding='utf-8')

    analyzed = []
    for t in topics:
        res = analyze_with_grok(t, retries=3)
        model_used = f'grok:{GROK_MODEL}'
        if not res:
            res = analyze_with_google(t)
            model_used = 'google:3.1-flash-fallback'
        if not res:
            analyzed.append({'topic': t, 'ok': False, 'error': 'analysis_failed'})
            continue
        analyzed.append({'topic': t, 'ok': True, 'analysis': res, 'model': model_used})

    ok_items = [x for x in analyzed if x.get('ok')]

    for idx, item in enumerate(ok_items, 1):
        title = item['topic'].get('title', f'topic-{idx}')
        idea = item['analysis'].get('comicIdea', item['analysis'].get('angleSuggestions', [''])[0])
        out = IMG_DIR / day / 'auto' / f'auto_{hour}_{idx:02d}.png'
        item['imageOk'] = gen_image_google(title, str(idea), out)
        item['imagePath'] = str(out) if item['imageOk'] else ''

    analysis_path = ANALYSIS_DIR / day / f'{hour}.json'
    analysis_path.write_text(json.dumps({'timestamp': stamp, 'mode': args.mode, 'items': analyzed}, ensure_ascii=False, indent=2), encoding='utf-8')

    # daily markdown
    daily_md = DAILY_DIR / f'{day}.md'
    lines = [f'## {stamp} [{args.mode}]\n']
    for i, item in enumerate(ok_items, 1):
        a = item['analysis']
        lines.append(f"{i}. {item['topic'].get('title','(no title)')}")
        lines.append(f"   - 分类: {a.get('category','')}, 情绪: {a.get('emotionScore','')}, 风险: {a.get('riskLevel','')}")
        lines.append(f"   - 角度: {', '.join(a.get('angleSuggestions',[]))}")
        lines.append(f"   - 文案: {a.get('caption','')}")
        if item.get('imageOk'):
            lines.append(f"   - 图片: {item.get('imagePath','')}")
    lines.append('')
    with daily_md.open('a', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    queue_md = QUEUE_DIR / f'{day}.md'
    qlines = [f'## {stamp} 候选入队\n']
    for i, item in enumerate(ok_items, 1):
        a = item['analysis']
        qlines.append(f"- [{a.get('category','未分类')}] {item['topic'].get('title','')}")
        qlines.append(f"  - 推文: {a.get('caption','')}")
        qlines.append(f"  - 两格: {a.get('comicIdea','')}")
    qlines.append('')
    with queue_md.open('a', encoding='utf-8') as f:
        f.write('\n'.join(qlines) + '\n')

    print(json.dumps({
        'ok': True,
        'mode': args.mode,
        'raw': str(raw_path),
        'analysis': str(analysis_path),
        'daily': str(daily_md),
        'queue': str(queue_md),
        'successCount': len(ok_items),
        'total': len(topics),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('pipeline_error', str(e))
        traceback.print_exc()
        raise
