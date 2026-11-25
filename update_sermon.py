#!/usr/bin/env python3
"""가장 최근 주일 설교를 교회 유튜브 채널에서 찾아 홈페이지에 반영합니다.

사용법:  python3 update_sermon.py

하는 일
  1) 교회 유튜브 채널의 최근 영상 가운데 제목이 '… | 오륜교회 주일설교 (YYYY-MM-DD)' 인 가장 새 영상을 찾습니다.
  2) data/sermon.js (말씀 장면) 를 그 설교로 바꾸고, 대표 사진을 data/sermon-poster.jpg 로 받습니다.
  3) data/videos.js 의 '주일예배' 목록 맨 위에 한 줄을 더합니다. (이미 있으면 그대로 둡니다)

깃허브에서 매주 월요일 아침에 자동으로 실행됩니다 (.github/workflows/sermon.yml).
새 설교가 없거나 채널을 읽지 못하면 아무것도 바꾸지 않습니다.
"""
import html, json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CHANNEL = 'UCCATFGVyXoa361VN6lELz3w'
FEED = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + CHANNEL
TITLE = re.compile(r'^(.*?)\s*-\s*([^|]*?)\s*\|\s*오륜교회\s*주일\s*설교\s*\((\d{4}-\d{2}-\d{2})\)\s*$')


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=40).read()


def latest():
    x = get(FEED).decode('utf-8', 'replace')
    found = []
    for e in re.findall(r'<entry>(.*?)</entry>', x, re.S):
        vid = re.search(r'<yt:videoId>([\w-]{11})<', e)
        t = re.search(r'<title>(.*?)</title>', e, re.S)
        if not vid or not t:
            continue
        m = TITLE.match(html.unescape(t.group(1)).strip())
        if not m:
            continue
        d = re.search(r'<media:description>(.*?)</media:description>', e, re.S)
        desc = html.unescape(d.group(1)) if d else ''
        line = lambda k: (re.search(r'^\s*%s\s*[:：]\s*(.+?)\s*$' % k, desc, re.M) or [None, ''])[1]
        who = line('설교') or m.group(2)
        name = re.sub(r'\s*\(.*', '', who).strip()                      # 주경훈 목사
        short = re.sub(r'\s*(담임목사|설립목사|목사|전도사|선교사|교수)$', '', name)  # 주경훈
        role = '담임목사' if '담임목사' in who else '설립목사' if '설립목사' in who else ''
        found.append({
            'date': m.group(3), 'youtube': vid.group(1),
            'title': (line('제목') or m.group(1)).strip(),
            'scripture': line('본문'),
            'preacher': (short + ' ' + role) if role else name,
            'short': short,
        })
    found.sort(key=lambda s: s['date'], reverse=True)
    return found[0] if found else None


def js(s):
    return "'" + s.replace('\\', '\\\\').replace("'", "\\'") + "'"


def main():
    try:
        s = latest()
    except Exception as e:
        print('채널을 읽지 못했습니다:', e)
        return 1
    if not s:
        print('주일 설교 영상을 찾지 못했습니다. 바꾸지 않습니다.')
        return 0
    path = os.path.join(ROOT, 'data', 'sermon.js')
    old = open(path, encoding='utf-8').read()
    cur = re.search(r"youtube:\s*'([\w-]+)'", old)
    cur_date = re.search(r"date:\s*'([\d-]+)'", old)
    if cur and cur.group(1) == s['youtube']:
        print('이미 최신입니다:', s['date'], s['title'])
    elif cur_date and cur_date.group(1) > s['date']:
        print('지금 올라가 있는 설교가 더 새것입니다. 바꾸지 않습니다.')
        return 0
    else:
        # 대표 사진
        for size in ('maxresdefault', 'sddefault', 'hqdefault'):
            try:
                img = get('https://i.ytimg.com/vi/%s/%s.jpg' % (s['youtube'], size))
                if len(img) > 8000:
                    open(os.path.join(ROOT, 'data', 'sermon-poster.jpg'), 'wb').write(img)
                    break
            except Exception:
                pass
        head = ''.join(l for l in old.splitlines(True) if l.startswith('//'))
        body = ("window.SERMON = {\n  title: %s,\n  scripture: %s,\n  preacher: %s,\n  date: %s,\n"
                "  service: '주일예배',\n  youtube: %s,\n  poster: %s\n};\n") % (
            js(s['title']), js(s['scripture']), js(s['preacher']), js(s['date']), js(s['youtube']),
            js('data/sermon-poster.jpg?v=' + s['date'].replace('-', '')))
        open(path, 'w', encoding='utf-8').write(head + body)
        print('말씀 장면을 바꿨습니다:', s['date'], s['title'], '/', s['scripture'], '/', s['preacher'])

    # 설교 · 영상 모음의 주일예배 목록
    vp = os.path.join(ROOT, 'data', 'videos.js')
    v = open(vp, encoding='utf-8').read()
    if '"y":"%s"' % s['youtube'] not in v:
        key = '{"name":"주일예배","items":[\n'
        if key in v:
            row = json.dumps({'d': s['date'], 't': s['title'], 'y': s['youtube'],
                              's': ' · '.join(x for x in (s['scripture'], s['short']) if x)},
                             ensure_ascii=False, separators=(',', ':'))
            open(vp, 'w', encoding='utf-8').write(v.replace(key, key + row + ',\n', 1))
            print('영상 모음에 더했습니다.')
        else:
            print('영상 모음에서 주일예배 목록을 찾지 못해 건너뜁니다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
