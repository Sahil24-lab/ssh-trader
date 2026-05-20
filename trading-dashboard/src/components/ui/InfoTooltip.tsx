"use client";

import { ReactNode, useState } from "react";
import { createPortal } from "react-dom";

type InfoTooltipProps = {
  content: ReactNode;
  children?: ReactNode;
  className?: string;
};

export function InfoTooltip({ content, children = "?", className = "" }: InfoTooltipProps) {
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const canRenderTooltip = isOpen && anchorRect && typeof document !== "undefined";
  const left = anchorRect ? Math.min(window.innerWidth - 304, Math.max(16, anchorRect.left)) : 16;
  const top = anchorRect ? anchorRect.bottom + 8 : 16;

  return (
    <span
      className={`inline-flex ${className}`}
      onMouseEnter={(event) => {
        setAnchorRect(event.currentTarget.getBoundingClientRect());
        setIsOpen(true);
      }}
      onMouseLeave={() => setIsOpen(false)}
      onFocus={(event) => {
        setAnchorRect(event.currentTarget.getBoundingClientRect());
        setIsOpen(true);
      }}
      onBlur={() => setIsOpen(false)}
    >
      <span className="inline-flex">{children}</span>
      {canRenderTooltip
        ? createPortal(
            <span
              className="pointer-events-none fixed z-[10000] w-72 rounded-lg border border-primary/35 bg-[#07131f] p-3 text-left text-[12px] font-normal normal-case leading-relaxed tracking-normal text-textMuted shadow-2xl shadow-black/70"
              style={{ left, top }}
            >
              {content}
            </span>,
            document.body
          )
        : null}
    </span>
  );
}
