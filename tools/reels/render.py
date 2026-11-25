"""릴스 렌더러: HTML 장면(tools/reels/*.html)을 브라우저(Chromium)로 한 프레임씩 그려 MP4로 묶는다.
HTML 안의 render(t) 함수가 t초 화면을 그린다. 무료(Playwright + ffmpeg), 외부 API 없음.

  python tools/reels/render.py weather data.json out.mp4
"""
import json, os, subprocess, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30


def warp(T, holds):
    """실제 시각 T → 장면 시각 t. holds=[[장면 t, 멈출 초], ...]: 그 순간에서 화면을 멈춰 읽을 시간을 준다."""
    t = T
    for at, d in sorted(holds):
        if t <= at: break
        t = at if t < at + d else t - d
    return t


def render(scene, data, out, seconds=10.0, fps=FPS):
    holds = data.get("holds", [])
    seconds = data.get("seconds", seconds) + sum(d for _, d in holds)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps),
                           "-c:v", "mjpeg", "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.add_init_script(f"window.DATA = {json.dumps(data, ensure_ascii=False)};")
        pg.goto(f"file://{HERE}/{scene}.html")
        pg.wait_for_function("window.READY === true")
        for i in range(int(seconds * fps)):
            pg.evaluate(f"render({warp(i / fps, holds)}, {i / fps})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=95))
        b.close()
    ff.stdin.close(); ff.wait()


if __name__ == "__main__":
    scene, data, out = sys.argv[1:4]
    render(scene, json.load(open(data, encoding="utf-8")), out)
