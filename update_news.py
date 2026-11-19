#!/usr/bin/env python3
"""소식 폴더를 읽어 홈페이지 '소식'에 반영합니다.

사용법:  python3 update_news.py

자료 폴더(아래 SOURCES) 안에 종류별 폴더가 있습니다.
    공지/  행사/  교우소식/  주보/  QT/

글 하나는 다음 둘 중 하나로 넣습니다. 이름 맨 앞에 날짜(YYYY-MM-DD)를 적습니다.
  1) 파일 하나:   2026-11-19 추수감사주일 안내.txt   (또는 .jpg .png .pdf)
  2) 폴더 하나:   2026-11-19 추수감사주일 안내/      (안에 글.txt 와 사진, PDF 를 함께)
행사는 '2026-11-01~2026-11-30 제목' 처럼 기간을 적을 수 있습니다.

실행하면 사진은 웹용으로 줄여 news/ 폴더에 담고, 목록은 data/news.js 에 기록합니다.
종류마다 최근 글 30개까지 올라갑니다. 자료 폴더에서 지운 글은 다음 실행 때 홈페이지에서도 빠집니다.
"""
import hashlib, json, os, re, shutil, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
# 자료를 읽는 곳. 있는 폴더는 모두 읽어 합칩니다. (나스 폴더가 연결돼 있지 않으면 건너뜁니다)
SOURCES = ['/Volumes/ORYUN AITEAM/홈페이지/소식', os.path.join(ROOT, '소식자료')]
CATS = [('notice', '공지'), ('event', '행사'), ('family', '교우소식'), ('bulletin', '주보'), ('qt', 'QT')]
IMG = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.gif'}
DOC = {'.pdf', '.hwp', '.hwpx', '.docx', '.xlsx', '.pptx', '.zip'}
LIMIT = 30
nfc = lambda x: unicodedata.normalize('NFC', x)


def parse_name(name):
    m = re.match(r'(\d{4}-\d{2}-\d{2})(?:\s*~\s*(\d{4}-\d{2}-\d{2}))?\s*(.*)', name)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3).strip() or m.group(1)


def collect():
    posts = {k: {} for k, _ in CATS}
    for src in SOURCES:
        if not os.path.isdir(src):
            continue
        for key, folder in CATS:
            d = next((os.path.join(src, f) for f in os.listdir(src) if nfc(f) == folder), None)
            if not d or not os.path.isdir(d):
                continue
            for entry in os.listdir(d):
                if entry.startswith('.'):
                    continue
                path = os.path.join(d, entry)
                stem = nfc(entry if os.path.isdir(path) else os.path.splitext(entry)[0])
                info = parse_name(stem)
                if not info:
                    print('  건너뜀 (이름 앞에 날짜가 없음): %s/%s' % (folder, nfc(entry)))
                    continue
                post = posts[key].setdefault(stem, {'d': info[0], 'e': info[1], 't': info[2], 'files': []})
                files = sorted(os.path.join(path, f) for f in os.listdir(path) if not f.startswith('.')) if os.path.isdir(path) else [path]
                post['files'] += files
    return posts


def build():
    out_dir = os.path.join(ROOT, 'news')
    keep = set()
    data = []
    for key, name in CATS:
        items = []
        for stem, post in sorted(collect_cache[key].items(), key=lambda kv: kv[1]['d'], reverse=True)[:LIMIT]:
            sid = hashlib.md5(stem.encode('utf-8')).hexdigest()[:10]
            item = {'d': post['d'], 't': post['t']}
            if post['e']:
                item['e'] = post['e']
            body, imgs, docs = [], [], []
            for f in post['files']:
                ext = os.path.splitext(f)[1].lower()
                if ext in ('.txt', '.md'):
                    body.append(open(f, encoding='utf-8', errors='replace').read().strip())
                elif ext in IMG:
                    rel = 'news/%s/%s-%d.jpg' % (key, sid, len(imgs) + 1)
                    dst = os.path.join(ROOT, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(f):
                        r = subprocess.run(['sips', '-Z', '1600', '-s', 'format', 'jpeg', '-s', 'formatOptions', '82', f, '--out', dst], capture_output=True)
                        if r.returncode != 0:
                            print('  사진 변환 실패: %s' % nfc(os.path.basename(f)))
                            continue
                    imgs.append(rel); keep.add(dst)
                elif ext in DOC:
                    rel = 'news/%s/%s-%d%s' % (key, sid, len(docs) + 1, ext)
                    dst = os.path.join(ROOT, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(f):
                        shutil.copy2(f, dst)
                    docs.append({'n': nfc(os.path.basename(f)), 'u': rel}); keep.add(dst)
            if body:
                item['b'] = '\n\n'.join(x for x in body if x)
            if imgs:
                item['i'] = imgs
            if docs:
                item['f'] = docs
            items.append(item)
        data.append({'key': key, 'name': name, 'items': items})
        print('%s  %d개' % (name, len(items)))
    # 더 이상 쓰지 않는 파일 정리
    if os.path.isdir(out_dir):
        for base, _, files in os.walk(out_dir):
            for f in files:
                if os.path.join(base, f) not in keep:
                    os.remove(os.path.join(base, f))
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    with open(os.path.join(ROOT, 'data', 'news.js'), 'w', encoding='utf-8') as fp:
        fp.write('// update_news.py 가 자동으로 만든 파일입니다. 직접 고치지 마세요.\n')
        fp.write('window.NEWS = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('},{"d"', '},\n{"d"') + ';\n')
    print('\ndata/news.js 를 갱신했습니다.')


if __name__ == '__main__':
    found = [s for s in SOURCES if os.path.isdir(s)]
    if not found:
        sys.exit('자료 폴더가 없습니다: ' + ' / '.join(SOURCES))
    print('읽는 곳: ' + ' , '.join(found))
    collect_cache = collect()
    build()
