import { useEffect, useState } from 'react';
import { Icon } from '../ui';
import type { Step } from './types';

type Props = {
  steps: Step[];
  thinking: string;
  live: boolean;
  startedAt?: number;
  seconds?: number;
};

// Reasoning can be long; while live, show only its tail.
const THINKING_TAIL = 280;

function useElapsedSeconds(startedAt: number | undefined, live: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [live]);
  return startedAt ? Math.max(0, Math.round((now - startedAt) / 1000)) : 0;
}

function StepRow({ step, running }: { step: Step; running: boolean }) {
  return (
    <li className="flex items-start gap-1.5">
      <span className="mt-0.5 w-3 flex-shrink-0">
        {running ? (
          <span className="block w-3 h-3 rounded-full border-2 border-fg-3 border-t-transparent animate-spin" />
        ) : step.ok === false ? (
          <span className="text-danger">
            <Icon name="alert-circle" size={12} color="currentColor" />
          </span>
        ) : (
          <Icon name="check" size={12} color="currentColor" />
        )}
      </span>
      <span className={running ? 'text-fg-2' : ''}>{step.label}</span>
    </li>
  );
}

// What the assistant is doing during a turn — like a coding agent's tool log —
// collapsing to a one-line summary once the turn is over.
export default function ActivityBlock({ steps, thinking, live, startedAt, seconds }: Props) {
  const [expanded, setExpanded] = useState(false);
  const elapsed = useElapsedSeconds(startedAt, live);
  const toolCount = `${steps.length} ${steps.length === 1 ? 'step' : 'steps'}`;

  if (!live) {
    return (
      <div className="text-xs text-fg-3">
        <button
          type="button"
          className="inline-flex items-center gap-1 hover:text-fg-1"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
        >
          <Icon name={expanded ? 'chevron-down' : 'chevron-right'} size={12} color="currentColor" />
          {toolCount}
          {seconds != null && ` · ${seconds}s`}
        </button>
        {expanded && (
          <ul className="mt-1 ml-4 space-y-0.5">
            {steps.map((step) => (
              <StepRow key={step.id} step={step} running={false} />
            ))}
          </ul>
        )}
      </div>
    );
  }

  const tail = thinking.length > THINKING_TAIL ? `…${thinking.slice(-THINKING_TAIL)}` : thinking;
  return (
    <div className="text-xs text-fg-3 space-y-1" data-testid="assistant-activity">
      <div className="flex items-center gap-1.5 text-fg-2">
        <span className="w-3 h-3 rounded-full border-2 border-primary-400 border-t-transparent animate-spin" />
        <span>Working · {elapsed}s</span>
      </div>
      {steps.length > 0 && (
        <ul className="ml-1 space-y-0.5">
          {steps.map((step) => (
            <StepRow key={step.id} step={step} running={step.ok === null} />
          ))}
        </ul>
      )}
      {tail && <div className="ml-1 italic whitespace-pre-wrap break-words line-clamp-3">{tail}</div>}
    </div>
  );
}
