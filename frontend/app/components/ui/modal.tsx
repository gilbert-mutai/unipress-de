"use client";

import { useEffect, useRef } from "react";
import { cn } from "../../lib/utils";
import { Button } from "./button";

/** A centred confirmation dialog.
 *
 * window.confirm cannot be styled, renders differently in every browser, and in a
 * screen recording it looks like the page has been interrupted by something else.
 * This keeps the decision inside the product.
 *
 * Centred rather than anchored: the question is blocking, so it should sit where
 * the eye already is instead of drawing it to a corner.
 */
export function ConfirmModal({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "caution",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "caution" | "neutral";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    // Escape cancels, which is what every dialog does and what a browser confirm
    // does; losing it would make this feel worse than what it replaced.
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    // Move focus into the dialog so the keyboard path works without a mouse.
    confirmRef.current?.focus();
    // Stop the page scrolling behind the overlay.
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      {/* Clicking away cancels, matching the Escape key. */}
      <button
        aria-label={cancelLabel}
        onClick={onCancel}
        className="absolute inset-0 cursor-default bg-ink/40 backdrop-blur-sm animate-fade-in"
      />
      <div className="animate-fade-up relative w-full max-w-md rounded-2xl border border-line bg-card p-5 shadow-xl">
        <h4 id="confirm-title" className="font-serif text-lg font-semibold text-ink">
          {title}
        </h4>
        <div className="mt-2 text-sm leading-relaxed text-muted">{body}</div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            ref={confirmRef}
            size="sm"
            variant={tone === "caution" ? "accent" : "primary"}
            onClick={onConfirm}
            className={cn(tone === "caution" && "font-semibold")}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
