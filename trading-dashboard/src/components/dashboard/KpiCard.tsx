import { ReactNode } from "react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

type Tone = "supportive" | "neutral" | "adverse";

type KpiCardProps = {
  label: string;
  value: string;
  tooltip: string;
  tone?: Tone;
  changeText?: string;
  isLoading?: boolean;
};

const changeToneStyles: Record<Tone, string> = {
  supportive: "text-supportive",
  neutral: "text-uiTextDim",
  adverse: "text-adverse"
};

export function KpiCard({
  label,
  value,
  tooltip,
  tone = "neutral",
  changeText,
  isLoading = false
}: KpiCardProps): ReactNode {
  return (
    <article
      className="relative min-h-[118px] rounded-[var(--radius-lg)] border border-uiBorderMedium bg-uiSurfaceGlassDeep px-4 py-4 shadow-[0_2px_16px_rgba(0,0,0,0.34)] transition duration-150 hover:border-uiBorderStrong hover:shadow-[0_4px_20px_rgba(0,0,0,0.38)]"
      aria-label={`${label}: ${tooltip}`}
    >
      <div className="mb-1 flex min-h-11 items-center gap-1 font-mono text-[0.58rem] font-medium uppercase tracking-[0.1em] text-[var(--text-label)]">
        {label}
        <InfoTooltip
          content={
            <span>
              <span className="block font-semibold text-uiTextPrimary">{label}</span>
              <span>{tooltip}</span>
            </span>
          }
        >
          <button
            type="button"
            className="inline-flex h-11 w-11 items-center justify-center rounded-full text-[10px] text-primary transition hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
            aria-label={`${label} information`}
          >
            ?
          </button>
        </InfoTooltip>
      </div>
      {isLoading ? (
        <>
          <div className="dashboard-skeleton mt-4 h-8 w-24 rounded" />
          <div className="dashboard-skeleton mt-3 h-3 w-16 rounded" />
        </>
      ) : (
        <div className="flex flex-col items-start">
          <p className="font-mono text-[1.35rem] font-bold leading-[1.15] text-uiTextPrimary">
            {value}
          </p>
          {changeText ? (
            <p className={`mt-2 font-mono text-[13px] font-semibold leading-none ${changeToneStyles[tone]}`}>
              {changeText}
            </p>
          ) : null}
        </div>
      )}
    </article>
  );
}
