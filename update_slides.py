#!/usr/bin/env python3
"""슬라이드 자료 폴더(slides/)를 읽어 홈페이지 배경에 반영합니다.

사용법:  python3 update_slides.py

slides/01-vision ~ 06-history 폴더마다 사진이나 영상을 넣어 두면,
폴더에서 가장 최근에 넣은 파일 하나를 그 슬라이드의 배경으로 씁니다.
  - 사진: 웹용 JPG(web.jpg)로 줄여서 저장
  - 영상: 소리를 뺀 720p 웹용(web.mp4)과 대표 이미지(web.jpg)로 변환 (ffmpeg 필요)
  - 폴더가 비어 있으면 기본 그래픽을 그대로 씁니다
결과는 slides/manifest.js 에 기록되고, index.html 이 그 파일을 읽습니다.
"""
import json, os, shutil, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
SLIDES = os.path.join(ROOT, 'slides')
FOLDERS = ['01-vision', '02-worship', '03-greeting', '04-people', '05-location', '06-history']
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.tif', '.tiff', '.arw', '.cr2', '.cr3', '.nef', '.dng'}
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.webm', '.mkv'}
GENERATED = {'web.jpg', 'web.mp4', 'options.json'}


def newest_source(folder):
    """폴더에서 가장 최근에 수정된 원본 파일(사진/영상)을 고른다."""
    best = None
    for name in os.listdir(folder):
        if name.startswith('.') or is_generated(name):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in IMAGE_EXT and ext not in VIDEO_EXT:
            continue
        path = os.path.join(folder, name)
        if best is None or os.path.getmtime(path) > os.path.getmtime(best):
            best = path
    return best


def is_generated(name):
    return name in GENERATED or (name.startswith('web-') and name.endswith('.jpg'))


def all_images(folder):
    """폴더 안의 원본 사진 전부 (이름순). 카드 배치용."""
    return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                  if not n.startswith('.') and not is_generated(n)
                  and os.path.splitext(n)[1].lower() in IMAGE_EXT)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('명령 실패: %s\n%s' % (' '.join(cmd[:3]), r.stderr[-600:]))


def needs_build(src, *outs):
    return any(not os.path.exists(o) or os.path.getmtime(o) < os.path.getmtime(src) for o in outs)


def brightness(jpg):
    """글자가 놓이는 왼쪽 아래 영역의 평균 밝기(0~255). Pillow 가 없으면 None."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return None
    im = Image.open(jpg).convert('L')
    w, h = im.size
    return ImageStat.Stat(im.crop((0, int(h * 0.35), int(w * 0.6), h))).mean[0]


def build():
    ffmpeg = shutil.which('ffmpeg') or ('/opt/homebrew/bin/ffmpeg' if os.path.exists('/opt/homebrew/bin/ffmpeg') else None)
    media = []
    for name in FOLDERS:
        folder = os.path.join(SLIDES, name)
        os.makedirs(folder, exist_ok=True)
        src = newest_source(folder)
        opt_path = os.path.join(folder, 'options.json')
        opts = json.load(open(opt_path, encoding='utf-8')) if os.path.exists(opt_path) else {}

        # 여러 장 배치: options.json 의 "layout" 이 "cards"(부채꼴 카드, 최대 5장) 또는
        # "slideshow"(화면 가득 확대되며 넘어가는 사진, 최대 12장) 이면 폴더의 사진을 이름순으로 모두 쓴다
        layout = opts.get('layout')
        if layout in ('cards', 'slideshow'):
            limit, size = (5, '1400') if layout == 'cards' else (12, '1920')
            imgs = all_images(folder)[:limit]
            for old in os.listdir(folder):
                if is_generated(old) and old != 'options.json':
                    os.remove(os.path.join(folder, old))
            items = []
            for k, img in enumerate(imgs, 1):
                out = os.path.join(folder, 'web-%d.jpg' % k)
                run(['sips', '-Z', size, '-s', 'format', 'jpeg', '-s', 'formatOptions', '82', img, '--out', out])
                url = 'slides/%s/web-%d.jpg?v=%d' % (name, k, int(os.path.getmtime(img)))
                # options.json 의 "focus": {"파일 이름 일부": "가로% 세로%"} → 그 사진을 화면에 맞춰 자를 때의 중심
                pos = next((v for key, v in (opts.get('focus') or {}).items()
                            if key in unicodedata.normalize('NFC', os.path.basename(img))), None)
                items.append({'src': url, 'position': pos} if pos else url)
            if items:
                tone = opts.get('tone') or ('light' if layout == 'cards' else 'dark')
                item = {'type': layout, 'tone': tone, 'items': items, 'alt': opts.get('alt', '')}
                if opts.get('dim'):
                    item['dim'] = opts['dim']
                media.append(item)
                print('%s  → %s %d장' % (name, '카드' if layout == 'cards' else '넘어가는 사진', len(items)))
                continue

        web_jpg = os.path.join(folder, 'web.jpg')
        web_mp4 = os.path.join(folder, 'web.mp4')
        if src is None:
            for f in (web_jpg, web_mp4):
                if os.path.exists(f):
                    os.remove(f)
            media.append({'type': 'none'})
            print('%s  → 자료 없음 (기본 그래픽)' % name)
            continue

        ext = os.path.splitext(src)[1].lower()
        is_video = ext in VIDEO_EXT
        if is_video:
            if not ffmpeg:
                sys.exit('영상을 변환하려면 ffmpeg 가 필요합니다 (brew install ffmpeg).')
            if needs_build(src, web_mp4, web_jpg):
                print('%s  영상 변환 중… (%s)' % (name, os.path.basename(src)))
                run([ffmpeg, '-loglevel', 'error', '-y', '-i', src, '-an',
                     '-vf', 'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=24',
                     '-c:v', 'libx264', '-preset', 'slow', '-crf', '27', '-pix_fmt', 'yuv420p',
                     '-movflags', '+faststart', web_mp4])
                run([ffmpeg, '-loglevel', 'error', '-y', '-ss', '3', '-i', src, '-frames:v', '1',
                     '-vf', 'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720', '-q:v', '4', web_jpg])
        else:
            if os.path.exists(web_mp4):
                os.remove(web_mp4)
            if needs_build(src, web_jpg):
                print('%s  사진 변환 중… (%s)' % (name, os.path.basename(src)))
                run(['sips', '-Z', '2400', '-s', 'format', 'jpeg', '-s', 'formatOptions', '85', src, '--out', web_jpg])

        tone = opts.get('tone')
        if tone not in ('dark', 'light'):
            b = brightness(web_jpg)
            tone = 'light' if (b is not None and b > 150) else 'dark'

        ver = int(os.path.getmtime(web_mp4 if is_video else web_jpg))
        item = {'type': 'video' if is_video else 'image', 'tone': tone}
        if is_video:
            item['src'] = 'slides/%s/web.mp4?v=%d' % (name, ver)
            item['poster'] = 'slides/%s/web.jpg?v=%d' % (name, ver)
        else:
            item['src'] = 'slides/%s/web.jpg?v=%d' % (name, ver)
        for key in ('dim', 'position', 'alt'):
            if opts.get(key):
                item[key] = opts[key]
        media.append(item)
        print('%s  → %s, 글자 %s  (%s)' % (name, '영상' if is_video else '사진',
                                        '흰색' if tone == 'dark' else '남색', os.path.basename(src)))

    out = os.path.join(SLIDES, 'manifest.js')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('// update_slides.py 가 자동으로 만든 파일입니다. 직접 고치지 마세요.\n')
        f.write('window.SLIDE_MEDIA = ' + json.dumps(media, ensure_ascii=False, indent=2) + ';\n')
    print('\nslides/manifest.js 를 갱신했습니다. 브라우저에서 새로고침해 확인하세요.')


if __name__ == '__main__':
    build()
