import React from 'react';

import type { ReportSingle, RuleResult } from '../../lib/foodplan';

// Leitet aus dem Score eine einfache Ampelfarbe für die Karte ab.
function ampelfarbe(score: number) {
  if (score >= 0.8) return { name: 'Grün', bg: '#16a34a' };
  if (score >= 0.6) return { name: 'Gelb', bg: '#f59e0b' };
  return { name: 'Rot', bg: '#dc2626' };
}

export function ScoreCard({
  title,
  rep,
}: {
  title: string;
  rep: ReportSingle;
}) {
  // Zeigt kompakt den Gesamtscore pro Ernährungsform.
  const s = rep.summary.score;
  const badge = ampelfarbe(s);

  return (
    <div className='rounded-xl border border-slate-300 bg-white p-3.5 text-slate-900'>
      <div className='flex items-center justify-between gap-3'>
        <div className='text-lg font-extrabold'>{title}</div>
        <div
          className='rounded-full px-2.5 py-1 text-sm font-extrabold text-white'
          style={{ background: badge.bg }}
        >
          {badge.name}
        </div>
      </div>

      <div className='mt-2.5 text-base font-bold'>
        {(s * 100).toFixed(1)}% ({rep.summary.passed_rules}/
        {rep.summary.applicable_rules})
      </div>
    </div>
  );
}

export function RulesList({
  rep,
  onlyFailed,
}: {
  rep: ReportSingle;
  onlyFailed: boolean;
}) {
  // Filtert auf anwendbare Regeln und optional nur Verstöße.
  const rules = rep.rules
    .filter((r: RuleResult) => r.applies)
    .filter((r: RuleResult) => (onlyFailed ? !r.passed : true));

  return (
    <div className='mt-2 grid gap-2'>
      {rules.map((r: RuleResult) => (
        <div
          key={r.id}
          className={
            'rounded-lg border border-slate-200 p-2.5 text-slate-900 ' +
            (r.passed
              ? 'bg-emerald-50 border-l-4 border-l-emerald-500'
              : 'bg-red-50 border-l-4 border-l-red-500')
          }
        >
          <div className='flex items-start justify-between gap-2'>
            <div className='text-sm font-bold leading-snug'>{r.label}</div>
            <div
              className={
                'rounded-full px-2 py-0.5 text-[11px] font-extrabold ' +
                (r.passed
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-red-100 text-red-800')
              }
            >
              {r.passed ? 'Erfüllt' : 'Nicht erfüllt'}
            </div>
          </div>

          {(r.expected !== undefined || r.actual !== undefined) && (
            <div className='mt-1.5 flex flex-wrap gap-1.5 text-[11px] text-slate-700'>
              <span className='rounded bg-white px-1.5 py-0.5 border border-slate-200'>
                Erwartet: <b>{r.expected ?? '-'}</b>
              </span>
              <span className='rounded bg-white px-1.5 py-0.5 border border-slate-200'>
                Ist: <b>{r.actual ?? '-'}</b>
              </span>
            </div>
          )}

          {r.notes && (
            <div className='mt-1.5 text-xs leading-snug text-slate-600'>
              {r.notes}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
