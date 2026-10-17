#!/usr/bin/env python3
"""Export the approved mobile frames without rerendering or changing the movie."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'output/ENADE.ADS-2026-abertura-3D-mobile-vertical.mp4'
DEST = ROOT / 'output/tiktok-frames-v1'
WIDTH, HEIGHT, FPS, COUNT = 720, 1280, 25, 380


def export_frames():
    DEST.mkdir(exist_ok=True)
    decoder = subprocess.Popen([
        'ffmpeg', '-v', 'error', '-threads', '1', '-i', str(SOURCE),
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', 'pipe:1',
    ], stdout=subprocess.PIPE)
    frame_size = WIDTH * HEIGHT * 3
    try:
        for atlas_index in range(COUNT // 4):
            atlas = Image.new('RGB', (WIDTH * 2, HEIGHT * 2))
            for cell in range(4):
                data = decoder.stdout.read(frame_size)
                if len(data) != frame_size:
                    raise RuntimeError('Incomplete mobile movie frame')
                frame = Image.frombytes('RGB', (WIDTH, HEIGHT), data)
                atlas.paste(frame, ((cell % 2) * WIDTH, (cell // 2) * HEIGHT))
                frame.close()
            atlas.save(DEST / f'{atlas_index:03d}.webp', quality=82, method=4)
            atlas.close()
            if atlas_index % 20 == 0:
                print(f'Exported {atlas_index + 1}/95 frame sheets', flush=True)
        if decoder.stdout.read(1) or decoder.wait() != 0:
            raise RuntimeError('Unexpected mobile movie length')
    finally:
        decoder.stdout.close()
        if decoder.poll() is None:
            decoder.kill()
            decoder.wait()
    manifest = {
        'width': WIDTH, 'height': HEIGHT, 'fps': FPS, 'frames': COUNT,
        'columns': 2, 'framesPerSheet': 4, 'duration': COUNT / FPS,
        'sourceSha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    }
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def export_page():
    source = (ROOT / 'index.html').read_text()
    cta = source.split('    // The CTA keeps its own clock without delaying or repeating the video.\n', 1)[1]
    cta = cta.split('    const videoSource = selectedSource.src;', 1)[0]
    cta = cta.replace('video.readyState', 'player.readyState').replace('video.currentTime', 'player.currentTime')
    cta = cta.replace('Number(video.dataset.ctaStart)', '13')
    script = '''
    import { createTikTokPlayer } from '/assets/tiktok-player.js';
    const stage = document.getElementById('stage');
    const canvas = document.getElementById('opening');
    stage.dataset.layout = 'mobile';
    const status = document.getElementById('status');
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const player = createTikTokPlayer(canvas, {
      manifest: '/output/tiktok-frames-v1/manifest.json',
      onTime: () => updateInvitation(),
      onError: () => { status.textContent = 'Não foi possível carregar a animação. Toque para tentar novamente.'; status.hidden = false; },
      onReady: () => { status.hidden = true; }
    });
    // The CTA keeps the approved lettering, timing and light independent of playback.
''' + cta + '''
    let enteredByClick = false;
    canvas.addEventListener('click', event => {
      if (event.detail > 1) return;
      const fullscreen = document.fullscreenElement || document.webkitFullscreenElement;
      if (!fullscreen && (stage.requestFullscreen || stage.webkitRequestFullscreen)) {
        enteredByClick = true;
        if (stage.requestFullscreen) stage.requestFullscreen({navigationUI:'hide'}).catch(() => {});
        else stage.webkitRequestFullscreen();
        if (player.paused && !player.ended) player.play();
      } else {
        enteredByClick = false;
        player.paused ? player.play() : player.pause();
      }
    });
    canvas.addEventListener('dblclick', () => {
      if (enteredByClick) return;
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    });
    document.addEventListener('keydown', event => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || event.target.closest('a,button,input,textarea,select')) return;
      if (event.key === ' ' || event.key.toLowerCase() === 'k') {
        event.preventDefault(); player.paused ? player.play() : player.pause();
      } else if (event.key.toLowerCase() === 'r') { player.seek(0); player.play(); }
    });
    motion.addEventListener('change', event => { if (event.matches) player.pause(); });
    player.start(!motion.matches);
    // A small public interface also allows deterministic frame checks.
    window.tiktokOpening = player;
'''
    source = re.sub(r'<video\b.*?</video>', '<canvas id="opening" width="720" height="1280" tabindex="0" role="img" aria-describedby="playback-help" aria-label="Abertura 3D vertical ENADE ADS 2026"></canvas>', source, count=1, flags=re.S)
    source = source.replace('video {', 'canvas {').replace('] video{', '] canvas{')
    source = source.replace('<main class="stage"', '<main data-player="tiktok-frames" class="stage"')
    source = re.sub(r'<script>.*?</script>', '<script type="module">' + script + '\n  </script>', source, count=1, flags=re.S)
    source = source.replace('Clique na animação para entrar em tela cheia. Pressione Espaço para pausar ou continuar, F para alternar a tela cheia e R para assistir novamente.', 'A animação preenche a janela. Toque para pausar ou continuar. O botão Jogar agora aparece ao final.')
    (ROOT / 'tiktok.html').write_text(source)


if __name__ == '__main__':
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {max(os.sched_getaffinity(0))})
    os.nice(12)
    export_frames()
    export_page()
    print('TikTok frames and isolated page ready.', flush=True)
