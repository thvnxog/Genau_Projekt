import React from 'react';
import { LoadingSpinner } from '../ui/LoadingSpinner';

// Kleine Navigationsleiste für den Upload/Report-Flow.
type Step = 'upload' | 'report';

type StepNavigationProps = {
  step: Step;
  loading: boolean;
  onBack: () => void;
  onNext: () => void;
};

export function StepNavigation({
  step,
  loading,
  onBack,
  onNext,
}: StepNavigationProps) {
  return (
    // Zeigt aktuellen Schritt und die Primäraktionen "Zurück/Weiter".
    <div className='flex flex-wrap items-center justify-between gap-2 rounded-xl border border-sky-100 bg-sky-50/80 p-3 text-left'>
      <div className='text-sm font-extrabold'>
        Schritt:{' '}
        <span className='font-black'>
          {step === 'upload' ? '1/3 Upload' : '2/3 Report'}
        </span>
      </div>

      <div className='flex flex-wrap gap-2'>
        <button
          type='button'
          className='cursor-pointer rounded-[10px] border border-slate-300 bg-white px-3 py-2 text-sm font-extrabold text-slate-900 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'
          disabled={step === 'upload' || loading}
          onClick={onBack}
        >
          Zurück
        </button>

        <button
          type='button'
          className='cursor-pointer rounded-[10px] border border-teal-700 bg-teal-700 px-3 py-2 text-sm font-extrabold text-white hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'
          disabled={loading}
          onClick={onNext}
        >
          {loading ? (
            <span className='inline-flex items-center gap-2'>
              <LoadingSpinner className='text-white' />
              Lade...
            </span>
          ) : step === 'upload' ? (
            'Weiter'
          ) : (
            'Weiter zum Selbstcheck'
          )}
        </button>
      </div>
    </div>
  );
}
