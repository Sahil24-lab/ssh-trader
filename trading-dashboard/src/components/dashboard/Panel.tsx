import { ReactNode } from "react";

type PanelProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
};

export function Panel({ title, subtitle, children, className = "", action }: PanelProps) {
  return (
    <section
      className={`min-w-0 rounded-[var(--radius-lg)] border border-uiBorderMedium bg-uiSurfaceGlassDeep p-4 shadow-[0_2px_16px_rgba(0,0,0,0.34)] ${className}`}
    >
      <div className="mb-3 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="font-display text-[15px] font-semibold tracking-tight text-uiTextPrimary">{title}</h2>
        </div>
        <div className="flex min-w-0 shrink-0 items-center gap-2">
          {subtitle ? (
            <p className="text-right text-[12px] font-semibold text-uiTextDim">{subtitle}</p>
          ) : null}
          {action}
        </div>
      </div>
      {children}
    </section>
  );
}
