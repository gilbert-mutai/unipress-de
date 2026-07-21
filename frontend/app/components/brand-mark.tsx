"use client";

import { useState } from "react";
import { ShieldCheck } from "./icons";

// Shows the University of Debrecen logo from /public if present
// (frontend/public/ud-logo.svg), else falls back to the shield mark.
export function BrandMark() {
  const [err, setErr] = useState(false);

  if (err) {
    return (
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand text-brand-fg">
        <ShieldCheck className="h-4 w-4" />
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/ud-logo.svg"
      alt="University of Debrecen"
      className="h-8 w-auto"
      onError={() => setErr(true)}
    />
  );
}
