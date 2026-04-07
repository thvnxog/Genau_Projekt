import React from 'react';

import type { AnalyzeResponse } from '../../lib/foodplan';
import { RulesList, ScoreCard } from './ReportCards';

// Gesamter Report-Bereich mit Warnhinweis, Wochenwahl und Regelübersicht.
type ReportSectionProps = {
  reportData: AnalyzeResponse;
  loading: boolean;
  missingFoodGroupCount: number;
  activeWeekIndex: number;
  setActiveWeekIndex: (index: number) => void;
  onGoToSelfcheck: () => void;
};

export function ReportSection({
  reportData,
  loading,
  missingFoodGroupCount,
  activeWeekIndex,
  setActiveWeekIndex,
  onGoToSelfcheck,
}: ReportSectionProps) {
  const calculationHint = reportData.calculation;

  return (
    <section className='grid gap-4.5'>
      {calculationHint?.mode === 'estimated' && (
        <div className='rounded-xl border border-sky-200 bg-sky-50 p-3 text-left text-slate-900'>
          <div className='text-sm font-extrabold text-slate-900'>
            Hinweis zur Gramm-Auswertung
          </div>
          <div className='mt-1 text-sm text-slate-800'>
            {calculationHint.note}
          </div>
          <div className='mt-1 text-xs text-slate-700'>
            Schulstufe: {calculationHint.school_level_label ?? 'unbekannt'}
            {typeof calculationHint.days_considered === 'number'
              ? ` · Berücksichtigte Tage: ${calculationHint.days_considered}`
              : ''}
          </div>
        </div>
      )}

      {/* Hinweis, wenn noch Items ohne Foodgroup im Plan sind. */}
      {missingFoodGroupCount > 0 && (
        <details className='rounded-xl border border-amber-200 bg-amber-50 p-3 text-left text-slate-900'>
          <summary className='cursor-pointer select-none rounded font-extrabold flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'>
            <span className='text-lg'>⚠️</span>
            <span>
              Hinweis – {missingFoodGroupCount} Gerichte ohne Zuordnung
            </span>
          </summary>

          <div className='mt-3 text-sm text-slate-800'>
            <div className='mb-2'>
              Für diese {missingFoodGroupCount} Gerichte konnte keine passende
              Lebensmittel-Gruppe erkannt werden. Du kannst die Zuordnungen im
              Selbstcheck ergänzen und den Report danach neu berechnen.
            </div>

            <button
              type='button'
              className='cursor-pointer rounded-[10px] border border-teal-700 bg-teal-700 px-3 py-2 text-sm font-extrabold text-white hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'
              disabled={loading}
              onClick={onGoToSelfcheck}
            >
              Jetzt überarbeiten
            </button>
          </div>
        </details>
      )}

      {/* Monatsmodus: Woche auswählen und den aktiven Wochenreport anzeigen. */}
      {reportData.mode === 'monthly_dual' && (
        <>
          <div className='rounded-xl border border-slate-200 bg-white p-3 text-left text-slate-900'>
            <div className='flex flex-wrap justify-center gap-2'>
              {reportData.weekly_reports.map((w, idx) => (
                <button
                  key={w.week_index}
                  type='button'
                  onClick={() => setActiveWeekIndex(idx)}
                  className={`cursor-pointer rounded-full border px-3 py-1 text-xs font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 ${
                    idx === activeWeekIndex
                      ? 'border-teal-700 bg-teal-700 text-white'
                      : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-50'
                  }`}
                >
                  {w.week_label || `Woche ${w.week_index + 1}`}
                </button>
              ))}
            </div>
          </div>

          {(() => {
            const activeWeek =
              reportData.weekly_reports[
                Math.min(
                  Math.max(activeWeekIndex, 0),
                  Math.max(0, reportData.weekly_reports.length - 1),
                )
              ];

            return (
              <>
                <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
                  <ScoreCard title='Mischkost' rep={activeWeek.mixed} />
                  <ScoreCard
                    title='Vegetarisch'
                    rep={activeWeek.ovo_lacto_vegetarian}
                  />
                </div>

                <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
                  <div>
                    <h2 className='text-lg font-black'>Regeln – Mischkost</h2>
                    <RulesList rep={activeWeek.mixed} onlyFailed={false} />
                  </div>

                  <div>
                    <h2 className='text-lg font-black'>Regeln – Vegetarisch</h2>
                    <RulesList
                      rep={activeWeek.ovo_lacto_vegetarian}
                      onlyFailed={false}
                    />
                  </div>
                </div>
              </>
            );
          })()}
        </>
      )}

      {/* Einzelwochenmodus: direkte Reportdarstellung ohne Wochenumschaltung. */}
      {reportData.mode === 'dual' && (
        <>
          <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
            <ScoreCard title='Mischkost' rep={reportData.mixed} />
            <ScoreCard
              title='Vegetarisch'
              rep={reportData.ovo_lacto_vegetarian}
            />
          </div>

          <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
            <div>
              <h2 className='text-lg font-black'>Regeln – Mischkost</h2>
              <RulesList rep={reportData.mixed} onlyFailed={false} />
            </div>

            <div>
              <h2 className='text-lg font-black'>Regeln – Vegetarisch</h2>
              <RulesList
                rep={reportData.ovo_lacto_vegetarian}
                onlyFailed={false}
              />
            </div>
          </div>
        </>
      )}
    </section>
  );
}
