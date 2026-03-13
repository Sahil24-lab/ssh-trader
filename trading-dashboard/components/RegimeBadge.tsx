/* 8.1 components/RegimeBadge.tsx */
type Regime = 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF';

export const RegimeBadge = ({ regime }: { regime: Regime }) => {
  const colors = {
    RISK_ON: 'bg-teal-600 text-white',
    NEUTRAL: 'bg-amber-600 text-white',
    RISK_OFF: 'bg-slate-600 text-slate-200',
  };
  return (
    <span
      className={`px-2 py-1 rounded-full text-sm font-medium ${colors[regime]}`}
    >
      {regime}
    </span>
  );
};
