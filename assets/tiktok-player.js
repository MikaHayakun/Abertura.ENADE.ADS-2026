// TikTok only: the app cannot promote a canvas to its native video player.
export function createTikTokPlayer(canvas, { manifest: manifestUrl, onTime, onError, onReady }) {
  const context = canvas.getContext('2d', { alpha: false });
  const sheets = new Map();
  const retryAfter = new Map();
  let manifest;
  let currentTime = 0;
  let paused = true;
  let ended = false;
  let lastTick = 0;
  let lastFrame = -1;
  let animation;
  let resumeOnVisible = false;
  let resumeOnPageShow = false;
  const base = manifestUrl.slice(0, manifestUrl.lastIndexOf('/') + 1);

  function releaseSheet(index, entry) {
    if (entry.image) {
      if (entry.image.close) entry.image.close();
      else entry.image.src = '';
    }
    sheets.delete(index);
  }

  function loadSheet(index) {
    if (index < 0 || index >= Math.ceil(manifest.frames / manifest.framesPerSheet)) return null;
    if (sheets.has(index)) return sheets.get(index);
    if ((retryAfter.get(index) || 0) > performance.now()) return { image: null, promise: Promise.resolve() };
    const entry = { image: null, promise: null };
    sheets.set(index, entry);
    entry.promise = fetch(base + String(index).padStart(3, '0') + '.webp', { cache: 'force-cache' })
      .then(response => { if (!response.ok) throw new Error('Frame sheet unavailable'); return response.blob(); })
      .then(async blob => {
        if (typeof createImageBitmap === 'function') {
          try { return await createImageBitmap(blob); } catch { /* Use the image decoder below. */ }
        }
        const url = URL.createObjectURL(blob);
        try {
          return await new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = () => resolve(image);
            image.onerror = reject;
            image.src = url;
          });
        } finally { URL.revokeObjectURL(url); }
      })
      .then(image => {
        if (sheets.get(index) !== entry) { if (image.close) image.close(); return; }
        retryAfter.delete(index);
        entry.image = image;
        onReady();
      })
      .catch(() => {
        if (sheets.get(index) === entry) sheets.delete(index);
        retryAfter.set(index, performance.now() + 1500);
        onError();
      });
    return entry;
  }

  function drawFrame(frame) {
    const index = Math.floor(frame / manifest.framesPerSheet);
    // Three decoded sheets bound memory; preloading keeps the next boundary ready.
    for (const [key, entry] of sheets) if (key < index || key > index + 2) releaseSheet(key, entry);
    const sheet = loadSheet(index);
    loadSheet(index + 1);
    loadSheet(index + 2);
    if (!sheet.image) return false;
    if (frame !== lastFrame) {
      const cell = frame % manifest.framesPerSheet;
      context.drawImage(sheet.image,
        (cell % manifest.columns) * manifest.width,
        Math.floor(cell / manifest.columns) * manifest.height,
        manifest.width, manifest.height, 0, 0, manifest.width, manifest.height);
      lastFrame = frame;
      canvas.dataset.frame = String(frame);
    }
    return true;
  }

  function tick(now) {
    if (paused) return;
    const elapsed = Math.max(0, Math.min((now - lastTick) / 1000, .1));
    const nextTime = Math.min(manifest.duration, currentTime + elapsed);
    lastTick = now;
    const frame = Math.min(manifest.frames - 1, Math.floor(nextTime * manifest.fps));
    // Loading pauses this clock, so the CTA never runs ahead of the actual picture.
    if (drawFrame(frame)) {
      currentTime = nextTime;
      onTime();
      if (currentTime >= manifest.duration) {
        ended = true;
        paused = true;
        return;
      }
    }
    animation = requestAnimationFrame(tick);
  }

  const player = {
    get currentTime() { return currentTime; },
    get duration() { return manifest?.duration || 15.2; },
    get readyState() { return manifest ? 2 : 0; },
    get paused() { return paused; },
    get ended() { return ended; },
    async start(autoplay) {
      try {
        const response = await fetch(manifestUrl, { cache: 'force-cache' });
        if (!response.ok) throw new Error('Manifest unavailable');
        manifest = await response.json();
        canvas.width = manifest.width;
        canvas.height = manifest.height;
        await loadSheet(0).promise;
        if (!drawFrame(0)) return;
        onTime();
        if (autoplay) player.play();
      } catch { onError(); }
    },
    async play() {
      if (!manifest) { player.start(true); return; }
      if (!paused) return;
      if (ended) await player.seek(0);
      paused = false;
      lastTick = performance.now();
      animation = requestAnimationFrame(tick);
    },
    pause() { paused = true; cancelAnimationFrame(animation); },
    async seek(seconds) {
      if (!manifest) return;
      currentTime = Math.max(0, Math.min(seconds, manifest.duration));
      ended = currentTime >= manifest.duration;
      const frame = Math.min(manifest.frames - 1, Math.floor(currentTime * manifest.fps));
      await loadSheet(Math.floor(frame / manifest.framesPerSheet)).promise;
      drawFrame(frame);
      lastTick = performance.now();
      onTime();
    }
  };
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { resumeOnVisible = !paused; player.pause(); }
    else if (resumeOnVisible) { resumeOnVisible = false; player.play(); }
  });
  window.addEventListener('pagehide', () => {
    resumeOnPageShow = !paused;
    player.pause();
    for (const [index, entry] of sheets) releaseSheet(index, entry);
  });
  window.addEventListener('pageshow', event => { if (event.persisted && resumeOnPageShow && !ended) player.play(); });
  return player;
}
