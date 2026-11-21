#!/usr/bin/env python3
"""기존 홈페이지(oryun.org)에서 매일 바뀌는 자료를 받아 새 홈페이지 소식에 반영합니다.

사용법:  python3 sync_old_site.py            받아서 반영하고 올리기까지
         python3 sync_old_site.py --no-push  받아서 반영만 (올리지 않음)

받는 것:  오늘의 QT (그날 1건) · 교우소식 (최근 30건) · 주보 (이번 달과 지난달)
받은 자료는 소식자료/ 폴더에 쌓이고, update_news.py 가 홈페이지에 반영합니다.
새 홈페이지로 전환해 기존 홈페이지가 닫히면 이 파일은 더 쓰지 않습니다.
"""
import datetime, html, os, re, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, '소식자료')
B = 'https://oryun.org'
op = urllib.request.build_opener(); op.addheaders = [('User-Agent', 'Mozilla/5.0')]
get = lambda u: op.open(u if u.startswith('http') else B + u, timeout=90).read()
txt = lambda x: re.sub(r'[ \t\xa0]+', ' ', html.unescape(re.sub(r'<[^>]+>', '', x))).strip()
safe = lambda x: re.sub(r'[\\/:*?"<>|]', ' ', x).strip()
lines = lambda x: '\n'.join(l for l in (txt(p) for p in re.sub(r'<(br|/p|/div|/li|/dd|/dt)[^>]*>', '\n', x).split('\n')) if l)
today = datetime.date.today()


def qt():
    h = get('/life/?menu=248').decode('utf-8', 'replace')
    h = re.sub(r'<script.*?</script>', '', h, flags=re.S)
    m = re.search(r'<div class="jumanna1">.*?<dt>\s*(\d{1,2})\.(\d{1,2})\s*<span>(.*?)</span>.*?<p class="ptitle">(.*?)<span>(.*?)</span>', h, re.S)
    if not m:
        print('QT: 화면 구조가 달라 받지 못했습니다'); return 0
    mm, dd, wd, title, ref = int(m.group(1)), int(m.group(2)), txt(m.group(3)), txt(m.group(4)), txt(m.group(5))
    yy = today.year - 1 if (mm == 12 and today.month == 1) else today.year
    out = ['%s · %s' % (ref, wd), '']
    b1 = re.search(r'<div class="jumanna2Box1">(.*?)</div>', h, re.S)
    if b1:
        t = re.search(r'<p class="tit">(.*?)</p>', b1.group(1), re.S)
        if t: out += ['[본문] ' + txt(t.group(1))]
        for n, v in re.findall(r'<li><em>(.*?)</em>(.*?)</li>', b1.group(1), re.S):
            if txt(n) == '-': break          # 여기부터는 영어 본문
            out.append('%s %s' % (txt(n), txt(v)))
        out.append('')
    i = h.find('<div class="jumanna2Box2">'); j = h.find('정기구독 신청', i)
    seg = h[i:j if j > 0 else i + 12000] if i > 0 else ''
    for dt, dd_ in re.findall(r'<dt>(.*?)</dt>\s*(?:<dd>(.*?)</dd>)?', seg, re.S):
        head = re.search(r'<p class="dt_tit">(.*?)</p>', dt, re.S) or re.search(r'<b>(.*?)</b>', dt, re.S)
        name = txt(head.group(1)) if head else ''
        if name in ('큐티나눔', '주만나', ''): continue
        body = lines(dt.replace(head.group(0), '') + (dd_ or ''))
        body = '\n'.join(l for l in body.split('\n') if not re.fullmatch(r'\d+ / \d+|등록 취소|등록|취소', l))
        if body: out += ['[%s]' % name, body, '']
    d = os.path.join(SRC, 'QT'); os.makedirs(d, exist_ok=True)
    name = '%04d-%02d-%02d %s (%s).txt' % (yy, mm, dd, safe(title), safe(ref))
    open(os.path.join(d, name), 'w', encoding='utf-8').write('\n'.join(out).strip() + '\n')
    print('QT:', name); return 1


def family():
    got = []
    for pg in (1, 2, 3, 4):
        h = get('/life/?menu=247&page=%d' % pg).decode('utf-8', 'replace')
        for bid, part, title, date, body in re.findall(r'<li class="friendsSub" data="(\d+)">.*?<span class="title_notice">\s*(?:<em[^>]*>(.*?)</em>)?(.*?)</span>.*?<span class="date3">([\d-]+)</span>.*?<span class="text2">(.*?)</span>\s*</div>', h, re.S):
            if not any(g[0] == bid for g in got):
                got.append((bid, txt(part), txt(title), date, lines(body)))
        if len(got) >= 30: break
    d = os.path.join(SRC, '교우소식'); os.makedirs(d, exist_ok=True)
    for bid, part, title, date, t in got[:30]:
        name = ('%s %s' % (date, safe(('[%s] ' % part if part else '') + title)))[:90].strip()
        open(os.path.join(d, name + '.txt'), 'w', encoding='utf-8').write(t + '\n')
    print('교우소식: %d건' % len(got[:30])); return len(got[:30])


def bulletin():
    n = 0
    prev = (today.replace(day=1) - datetime.timedelta(days=1))
    for yy, mm in ((prev.year, prev.month), (today.year, today.month)):
        h = get('/life/?menu=255&yy=%d&mm=%d' % (yy, mm)).decode('utf-8', 'replace')
        ids = re.findall(r'<li class="bulletin[^"]*" data="(\d+)">.*?<span class="date">([\d-]+)</span>', h, re.S)
        pdf = dict(re.findall(r'pdf\[(\d+)\] = "(\d+)"', h))
        photo = dict(re.findall(r"photo\[(\d+)\] = '(.*?)';", h))
        for bid, md in ids:
            d = os.path.join(SRC, '주보', '%d-%s 주보' % (yy, md)); os.makedirs(d, exist_ok=True)
            for k, s in enumerate(re.findall(r'src="([^"]+)"', photo.get(bid, '')), 1):
                p = os.path.join(d, '%02d.jpg' % k)
                if not os.path.exists(p): open(p, 'wb').write(get(s)); n += 1
            p = os.path.join(d, '%d-%s 주보.pdf' % (yy, md))
            if pdf.get(bid) and not os.path.exists(p):
                data = get('/down/bbs/' + pdf[bid])
                if data[:4] == b'%PDF': open(p, 'wb').write(data); n += 1
    print('주보: 새 파일 %d개' % n); return n


def git(*a, inp=None, timeout=900):
    r = subprocess.run(['git', '-C', ROOT] + list(a), input=inp, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0: raise RuntimeError('git %s: %s' % (a[0], (r.stderr or r.stdout).strip()[:300]))
    return r.stdout.strip()


def publish():
    """바탕화면이 아이클라우드라 git add/commit 이 멈추곤 해서, 바뀐 파일만 직접 등록해 올립니다."""
    files = ['data/news.js']
    for base, _, fs in os.walk(os.path.join(ROOT, 'news')):
        files += [os.path.relpath(os.path.join(base, f), ROOT) for f in fs if not f.startswith('.')]
    gone = [f for f in git('ls-files', 'news').split('\n') if f and not os.path.exists(os.path.join(ROOT, f))]
    git('update-index', '--add', '--stdin', inp='\n'.join(files) + '\n')
    if gone: git('update-index', '--remove', '--stdin', inp='\n'.join(gone) + '\n')
    tree = git('write-tree'); head = git('rev-parse', 'HEAD')
    if tree == git('rev-parse', 'HEAD^{tree}'):
        print('바뀐 것이 없어 올리지 않았습니다.'); return
    msg = 'Sync daily devotional, member news and bulletins from the old site (%s)\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>' % today.isoformat()
    c = git('commit-tree', tree, '-p', head, '-m', msg)
    git('update-ref', 'refs/heads/main', c, head)
    git('push', '-q', 'origin', c + ':refs/heads/main')
    print('올렸습니다:', c[:7])


if __name__ == '__main__':
    for f in (qt, family, bulletin):
        try: f()
        except Exception as e: print('%s 실패: %s' % (f.__name__, e))
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'update_news.py')], capture_output=True, text=True)
    print(r.stdout.strip()[-400:] or r.stderr.strip()[-400:])
    if r.returncode == 0 and '--no-push' not in sys.argv:
        try: publish()
        except Exception as e: print('올리기 실패:', e)
