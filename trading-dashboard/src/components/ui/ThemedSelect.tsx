"use client";

export type ThemedSelectOption = {
  value: string;
  label: string;
};

type ThemedSelectProps = {
  "aria-label": string;
  value: string;
  options: ThemedSelectOption[];
  onChange: (value: string) => void;
  className?: string;
};

export function ThemedSelect({
  "aria-label": ariaLabel,
  value,
  options,
  onChange,
  className = ""
}: ThemedSelectProps) {
  return (
    <div className={`relative w-full ${className}`}>
      <select
        aria-label={ariaLabel}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full appearance-none rounded-lg border border-uiBorderMedium bg-[var(--bg-input)] pl-3 pr-10 font-mono text-sm text-uiTextPrimary outline-none transition hover:border-primary/35 focus:border-primary/60 focus:ring-2 focus:ring-primary/30"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute right-4 top-1/2 h-2.5 w-2.5 -translate-y-[65%] rotate-45 border-b-2 border-r-2 border-uiTextSecondary"
      />
    </div>
  );
}
