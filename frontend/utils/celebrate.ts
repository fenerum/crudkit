// A short confetti burst for a write the server marked worth celebrating
// (CrudKitSettings.celebrate or an action answering {"celebrate": true}).

const COLOR_VARS = ['--stage-blue', '--stage-violet', '--stage-amber', '--stage-green', '--stage-rose'];
const PIECES = 150;
const DURATION_MS = 2000;
const GRAVITY = 0.25;

type Piece = { x: number; y: number; vx: number; vy: number; angle: number; spin: number; size: number; color: string };

function themeColors(): string[] {
  const style = getComputedStyle(document.documentElement);
  const colors = COLOR_VARS.map((name) => style.getPropertyValue(name).trim()).filter(Boolean);
  return colors.length ? colors : ['#4BA3F5', '#9B6BFF', '#F5B544', '#3DD68C', '#F0616D'];
}

// Half the pieces fly up and inwards from each bottom corner.
function launch(width: number, height: number, colors: string[]): Piece[] {
  return Array.from({ length: PIECES }, (_, i) => {
    const fromLeft = i % 2 === 0;
    const speed = 12 + Math.random() * 10;
    const angle = (Math.PI / 180) * (55 + Math.random() * 25);
    return {
      x: fromLeft ? 0 : width,
      y: height,
      vx: Math.cos(angle) * speed * (fromLeft ? 1 : -1),
      vy: -Math.sin(angle) * speed,
      angle: Math.random() * Math.PI,
      spin: (Math.random() - 0.5) * 0.4,
      size: 6 + Math.random() * 6,
      color: colors[i % colors.length],
    };
  });
}

export function celebrate() {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;

  const canvas = document.createElement('canvas');
  canvas.dataset.ckConfetti = '';
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  Object.assign(canvas.style, { position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '9999' });
  document.body.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  const pieces = launch(canvas.width, canvas.height, themeColors());
  const start = performance.now();

  const frame = (now: number) => {
    const elapsed = now - start;
    if (!ctx || elapsed > DURATION_MS) {
      canvas.remove();
      return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.globalAlpha = Math.min(1, 2 * (1 - elapsed / DURATION_MS));
    for (const piece of pieces) {
      piece.vy += GRAVITY;
      piece.vx *= 0.99;
      piece.x += piece.vx;
      piece.y += piece.vy;
      piece.angle += piece.spin;
      ctx.save();
      ctx.translate(piece.x, piece.y);
      ctx.rotate(piece.angle);
      ctx.fillStyle = piece.color;
      ctx.fillRect(-piece.size / 2, -piece.size / 4, piece.size, piece.size / 2);
      ctx.restore();
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
