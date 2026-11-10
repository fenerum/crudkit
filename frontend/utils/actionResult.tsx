import type { QueryClient } from '@tanstack/react-query';
import type { NavigateFunction } from 'react-router-dom';
import { toast } from 'react-toastify';
import { isFrontendPath } from '../src/routes/is-frontend-path';
import { JOBS_KEY } from '../data/jobs';
import { url } from './urls';

// Render any http(s) URLs inside a toast message as clickable links, leaving the rest
// as plain text. Returns the original string when there's nothing to linkify.
function linkify(text: string) {
  const urlPattern = /(https?:\/\/[^\s]+)/g;
  if (!urlPattern.test(text)) return text;
  const parts = text.split(urlPattern);
  return (
    <>
      {parts.map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="underline">
            {part}
          </a>
        ) : (
          part
        )
      )}
    </>
  );
}

// Tells the person how a @crm_action went: its messages as toasts, its task in
// the tray, and where it sends them (`redirect`).
export function handleActionResult(response: any, navigate: NavigateFunction, queryClient: QueryClient) {
  if (response.messages && response.messages.length > 0) {
    response.messages.forEach((message: string) => {
      let displayMessage = message;
      if (message.startsWith('[') && message.endsWith(']')) {
        try {
          const parsed = JSON.parse(message.replace(/'/g, '"'));
          if (Array.isArray(parsed)) displayMessage = parsed[0] || message;
        } catch {
          const match = message.match(/\['(.*?)'\]/);
          if (match && match[1]) displayMessage = match[1];
        }
      }
      if (
        displayMessage.includes('required') ||
        displayMessage.includes('error') ||
        displayMessage.includes('invalid') ||
        displayMessage.includes('failed')
      ) {
        toast.error(linkify(displayMessage));
      } else {
        toast.info(linkify(displayMessage));
      }
    });
  } else if (response.job) {
    // Its progress shows in the task tray; fetch it in case the socket is down.
    queryClient.invalidateQueries({ queryKey: JOBS_KEY });
  } else {
    toast.success('Action completed successfully');
  }

  if (response.redirect) {
    if (response.open_in_new_tab) {
      window.open(response.redirect, '_blank', 'noopener,noreferrer');
    } else if (response.redirect.startsWith('http')) {
      window.location.href = response.redirect;
    } else if (response.redirect.startsWith('/')) {
      if (isFrontendPath(response.redirect)) {
        navigate(response.redirect);
      } else {
        window.location.href = response.redirect;
      }
    } else {
      navigate(url(response.redirect));
    }
  } else if (!response.job && (!response.messages || response.messages.length === 0)) {
    toast.warn('Action did not return redirect');
  }
}
