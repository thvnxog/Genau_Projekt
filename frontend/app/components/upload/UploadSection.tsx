import React, { useState } from 'react';
import type { SchoolLevel } from '../../lib/foodplan';

// Upload-Bereich für Datei-Auswahl per Klick oder Drag-and-Drop.
type UploadSectionProps = {
  file: File | null;
  isDragging: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  setFile: (file: File | null) => void;
  setIsDragging: (isDragging: boolean) => void;
  schoolLevel: SchoolLevel | null;
  setSchoolLevel: (level: SchoolLevel) => void;
  clearSelectedFile: () => void;
};

export function UploadSection({
  file,
  isDragging,
  fileInputRef,
  setFile,
  setIsDragging,
  schoolLevel,
  setSchoolLevel,
  clearSelectedFile,
}: UploadSectionProps) {
  const [showHelpModal, setShowHelpModal] = useState(false);

  // Nimmt beim Drop immer die erste Datei.
  function pickFirstFile(dt: DataTransfer | null): File | null {
    if (!dt) return null;
    const f = dt.files?.[0];
    return f ?? null;
  }

  return (
    // Kapselt den gesamten Upload-UI-Block inkl. Template-Link.
    <div className='mx-auto grid w-full max-w-205 justify-items-stretch gap-2'>
      <div className='flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2'>
        <div className='text-sm font-bold text-slate-800'>
          Neu hier? Kurzanleitung anzeigen
        </div>
        <button
          type='button'
          onClick={() => setShowHelpModal(true)}
          className='cursor-pointer rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-bold text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'
        >
          Hilfe
        </button>
      </div>

      {showHelpModal && (
        <div className='fixed inset-0 z-50 grid place-items-center bg-slate-900/45 p-4'>
          <div
            role='dialog'
            aria-modal='true'
            aria-label='Kurzanleitung zum Speiseplan-Check'
            className='w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-4 text-left text-slate-900 shadow-2xl'
          >
            <div className='flex items-start justify-between gap-2'>
              <div>
                <div className='text-base font-black'>
                  So startest du in 30 Sekunden
                </div>
                <div className='mt-1 text-sm text-slate-700'>
                  Upload, Stufe wählen, Report lesen - dann bei Bedarf im
                  Selbstcheck korrigieren.
                </div>
              </div>
              <button
                type='button'
                onClick={() => setShowHelpModal(false)}
                aria-label='Popup schliessen'
                className='cursor-pointer rounded-full border border-slate-300 bg-white px-2.5 py-1 text-xs font-bold text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'
              >
                Schliessen
              </button>
            </div>

            <div className='mt-3 grid gap-2 text-sm sm:grid-cols-3'>
              <div className='rounded-lg border border-sky-100 bg-sky-50 px-3 py-2'>
                <span className='font-black text-sky-700'>1</span> Vorlage
                hochladen
              </div>
              <div className='rounded-lg border border-sky-100 bg-sky-50 px-3 py-2'>
                <span className='font-black text-sky-700'>2</span> Stufe P oder
                S wählen
              </div>
              <div className='rounded-lg border border-sky-100 bg-sky-50 px-3 py-2'>
                <span className='font-black text-sky-700'>3</span> Report prüfen
              </div>
            </div>

            <div className='mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700'>
              Grammwerte werden im Report als Orientierung angezeigt
              (Ist/Ziel/Fehlt) und helfen beim Nachsteuern.
            </div>
          </div>
        </div>
      )}

      <div className='font-extrabold'>Datei hochladen</div>

      <input
        ref={fileInputRef}
        type='file'
        accept='.xlsx,.json,application/json'
        className='hidden'
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      <div
        role='button'
        tabIndex={0}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            fileInputRef.current?.click();
          }
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsDragging(false);
          const dropped = pickFirstFile(e.dataTransfer);
          if (dropped) setFile(dropped);
        }}
        className={
          'relative grid min-h-35 w-full cursor-pointer select-none place-items-center rounded-xl border-2 border-dashed p-4.5 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 ' +
          (isDragging
            ? 'border-teal-600 bg-teal-50'
            : 'border-sky-200 bg-sky-50')
        }
      >
        {file && (
          <button
            type='button'
            aria-label='Datei entfernen'
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              clearSelectedFile();
            }}
            className='absolute right-2.5 top-2.5 grid h-7.5 w-7.5 cursor-pointer place-items-center rounded-full border border-sky-200 bg-white text-slate-900 hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'
          >
            <svg
              width='16'
              height='16'
              viewBox='0 0 24 24'
              fill='none'
              xmlns='http://www.w3.org/2000/svg'
            >
              <path
                d='M18 6L6 18'
                stroke='currentColor'
                strokeWidth='2.5'
                strokeLinecap='round'
              />
              <path
                d='M6 6L18 18'
                stroke='currentColor'
                strokeWidth='2.5'
                strokeLinecap='round'
              />
            </svg>
          </button>
        )}

        <div className='grid justify-items-center gap-2'>
          {file ? (
            <div className='text-sm font-extrabold'>{file.name}</div>
          ) : (
            <div
              aria-hidden='true'
              className='grid h-11 w-11 place-items-center rounded-full border border-sky-200 bg-white text-slate-900'
            >
              <svg
                width='22'
                height='22'
                viewBox='0 0 24 24'
                fill='none'
                xmlns='http://www.w3.org/2000/svg'
              >
                <path
                  d='M12 16V4'
                  stroke='currentColor'
                  strokeWidth='2'
                  strokeLinecap='round'
                />
                <path
                  d='M7 9L12 4L17 9'
                  stroke='currentColor'
                  strokeWidth='2'
                  strokeLinecap='round'
                  strokeLinejoin='round'
                />
                <path
                  d='M4 20H20'
                  stroke='currentColor'
                  strokeWidth='2'
                  strokeLinecap='round'
                />
              </svg>
            </div>
          )}
        </div>
      </div>

      <div className='rounded-xl border border-slate-200 bg-white p-3 text-left'>
        <div className='text-sm font-extrabold text-slate-900'>
          Stufe für die Auswertung wählen
        </div>
        <div className='mt-2 flex flex-wrap gap-2'>
          <button
            type='button'
            onClick={() => setSchoolLevel('P')}
            className={`cursor-pointer rounded-full border px-3 py-1.5 text-xs font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 ${
              schoolLevel === 'P'
                ? 'border-teal-700 bg-teal-700 text-white'
                : 'border-slate-300 bg-white text-slate-900 hover:bg-slate-50'
            }`}
            aria-pressed={schoolLevel === 'P'}
          >
            Primarstufe (P)
          </button>

          <button
            type='button'
            onClick={() => setSchoolLevel('S')}
            className={`cursor-pointer rounded-full border px-3 py-1.5 text-xs font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 ${
              schoolLevel === 'S'
                ? 'border-teal-700 bg-teal-700 text-white'
                : 'border-slate-300 bg-white text-slate-900 hover:bg-slate-50'
            }`}
            aria-pressed={schoolLevel === 'S'}
          >
            Sekundarstufe (S)
          </button>
        </div>
      </div>

      <div className='rounded-xl border border-slate-200 bg-slate-50 p-3 text-left'>
        <div className='text-sm font-extrabold text-slate-900'>
          Vorlagen herunterladen
        </div>

        <div className='mt-2 flex flex-wrap gap-2'>
          <a
            href='/1_Wochen_Plan.xlsx'
            download
            className='inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-bold text-slate-900 shadow-sm hover:border-slate-400 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'
          >
            1-Wochen-Plan
          </a>

          <a
            href='/Speiseplan_Template_4T.xlsx'
            download
            className='inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-bold text-slate-900 shadow-sm hover:border-slate-400 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'
          >
            Monatsplan (4 Tage)
          </a>
          <a
            href='/Speiseplan_Template_Monat.xlsx'
            download
            className='inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-bold text-slate-900 shadow-sm hover:border-slate-400 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'
          >
            Monatsplan (5 Tage)
          </a>
        </div>
      </div>
    </div>
  );
}
