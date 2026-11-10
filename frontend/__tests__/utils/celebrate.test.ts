import { celebrate } from '../../utils/celebrate';

const confetti = () => document.querySelector('canvas[data-ck-confetti]');

function reducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({ matches }) as any;
}

describe('celebrate', () => {
  let frames: FrameRequestCallback[];

  beforeEach(() => {
    frames = [];
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => frames.push(callback));
    vi.spyOn(performance, 'now').mockReturnValue(0);
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      clearRect: vi.fn(), save: vi.fn(), restore: vi.fn(), translate: vi.fn(), rotate: vi.fn(), fillRect: vi.fn(),
    } as any);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    confetti()?.remove();
  });

  it('bursts confetti over the page, then cleans up', () => {
    reducedMotion(false);
    celebrate();
    expect(confetti()).not.toBeNull();

    frames.shift()!(500);
    expect(confetti()).not.toBeNull();

    frames.shift()!(5000);
    expect(confetti()).toBeNull();
  });

  it('stays still for people who prefer reduced motion', () => {
    reducedMotion(true);
    celebrate();
    expect(confetti()).toBeNull();
  });
});
