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
      className={`rounded-[10px] border border-uiBorderMedium bg-uiSurfaceGlassDeep p-4 shadow-2xl shadow-black/20 backdrop-blur-sm ${className}`}
    >
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[15px] font-bold tracking-tight text-uiTextPrimary">{title}</h2>
        </div>
        <div className="flex items-center gap-2">
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
