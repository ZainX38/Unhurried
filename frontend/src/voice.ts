// Bot lines spoken with the browser's speechSynthesis, one after another.
// `speaking` is what mutes the caller's outgoing audio.

const WORDS_PER_SECOND = 2.5;
const FALLBACK_SLACK_MS = 2000;

export class BotVoice {
  private pending = 0;
  private queue: Promise<void> = Promise.resolve();
  private generation = 0; // bumped by cancel(); queued lines from before are skipped
  private quietWaiters: Array<() => void> = [];

  constructor(private onSpeakingChange: (speaking: boolean) => void) {}

  get speaking(): boolean {
    return this.pending > 0;
  }

  say(line: string): void {
    const gen = this.generation;
    this.pending++;
    this.onSpeakingChange(true);
    this.queue = this.queue
      .then(() => (gen === this.generation ? speakOne(line) : undefined))
      .finally(() => this.finishOne());
  }

  /** Resolves once nothing is queued or being spoken. */
  whenQuiet(): Promise<void> {
    if (!this.speaking) return Promise.resolve();
    return new Promise((resolve) => this.quietWaiters.push(resolve));
  }

  cancel(): void {
    this.generation++;
    window.speechSynthesis.cancel();
  }

  private finishOne(): void {
    this.pending = Math.max(0, this.pending - 1);
    if (this.pending > 0) return;
    this.onSpeakingChange(false);
    const waiters = this.quietWaiters;
    this.quietWaiters = [];
    waiters.forEach((w) => w());
  }
}

function speakOne(line: string): Promise<void> {
  return new Promise((resolve) => {
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      resolve();
    };
    // Chrome sometimes never fires 'end'; give up after the line's estimated length + 2 s.
    const words = line.trim().split(/\s+/).length;
    const timer = setTimeout(done, (words / WORDS_PER_SECOND) * 1000 + FALLBACK_SLACK_MS);

    const u = new SpeechSynthesisUtterance(line);
    u.lang = "en-GB";
    u.onend = done;
    u.onerror = done;
    window.speechSynthesis.resume(); // un-sticks Chrome if it was left paused
    window.speechSynthesis.speak(u);
  });
}
