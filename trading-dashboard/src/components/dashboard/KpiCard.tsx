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
  supportive: "text-[#56D8C6]",
  neutral: "text-[#A7B2C4]",
  adverse: "text-[#EE6A7A]"
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
      className="relative min-h-[118px] rounded-[10px] border border-uiBorderMedium bg-uiSurfaceGlassDeep px-4 py-4 backdrop-blur-sm transition duration-150 hover:border-primary/25"
      aria-label={`${label}: ${tooltip}`}
    >
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.13em] text-uiTextDim">
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
            className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-primary/25 text-[9px] text-primary"
            aria-label={`${label} information`}
          >
            ?
          </button>
        </InfoTooltip>
      </p>
      {isLoading ? (
        <>
          <div className="dashboard-skeleton mt-4 h-8 w-24 rounded" />
          <div className="dashboard-skeleton mt-3 h-3 w-16 rounded" />
        </>
      ) : (
        <div className="flex flex-col items-start">
          <p className="font-mono text-[24px] font-bold leading-[1.15] text-uiTextPrimary">
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
