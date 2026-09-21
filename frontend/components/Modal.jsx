import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

// Open modals, innermost last. Only the top one reacts to Esc/backdrop clicks,
// so nested modals (e.g. inline create inside inline create) close one at a time.
const modalStack = [];

export function isModalOpen() {
  return modalStack.length > 0;
}

/**
 * Portaled to document.body so a modal containing a <form> is never nested
 * inside another form in the DOM. Note React events still bubble through the
 * portal along the component tree.
 */
export default function Modal({ onClose, className = "max-w-md", children }) {
  const idRef = useRef(Symbol("modal"));
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const id = idRef.current;
    modalStack.push(id);

    const onKeyDown = (e) => {
      // react-select prevents default on Esc when it closes its own menu.
      if (e.key !== "Escape" || e.defaultPrevented) return;
      if (modalStack[modalStack.length - 1] !== id) return;
      e.preventDefault();
      onCloseRef.current();
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      modalStack.splice(modalStack.indexOf(id), 1);
    };
  }, []);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={`rounded-lg border border-border-1 bg-bg-2 p-5 w-full ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
