"""릴스 렌더러: reels/story.html 장면을 브라우저(Chromium)로 한 프레임씩 찍어 MP4로 묶는다.
무료(Playwright + ffmpeg), 외부 API 없음. 1080x1920, 30fps, 무음 AAC 트랙 포함(Instagram 권장).

  python reels/render.py data.json out.mp4 [cover.jpg]
"""
import json, os, subprocess, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30


def render(data, out, cover=None, cover_at=None, fps=FPS):
    """data = {theme, scenes}. 반환: 영상 길이(초). cover_at초 화면을 cover(JPEG)로 저장."""
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.add_init_script(f"window.DATA = {json.dumps(data, ensure_ascii=False)};")
        pg.goto(f"file://{HERE}/story.html")
        pg.wait_for_function("window.READY === true", timeout=60000)
        total = pg.evaluate("window.TOTAL")
        if cover:
            pg.evaluate(f"render({cover_at if cover_at is not None else 2.0})")
            pg.screenshot(path=cover, type="jpeg", quality=92)
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
                               "-c:v", "mjpeg", "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps),
                               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        for i in range(int(total * fps)):
            pg.evaluate(f"render({i / fps})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=93))
        b.close()
    ff.stdin.close()
    if ff.wait() != 0: raise RuntimeError("ffmpeg 실패")
    return total


if __name__ == "__main__":
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(render(d, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
