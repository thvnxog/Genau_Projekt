'use client';

import React, { useRef, useState } from 'react';

type RuleResult = {
  id: string;
  label: string;
  applies: boolean;
  passed: boolean;
  expected?: string;
  actual?: number;
  notes?: string;
};

type ReportSingle = {
  summary: { score: number; passed_rules: number; applicable_rules: number };
  rules: RuleResult[];
};

type ReportDual = {
  mode: 'dual';
  mixed: ReportSingle;
  ovo_lacto_vegetarian: ReportSingle;
};

// Ampel-Logik: leitet aus dem Score (0..1) eine Farbe/Bezeichnung ab.
function ampelfarbe(score: number) {
  if (score >= 0.8) return { name: 'Grün', bg: '#16a34a' };
  if (score >= 0.6) return { name: 'Gelb', bg: '#f59e0b' };
  return { name: 'Rot', bg: '#dc2626' };
}

// ScoreCard: zeigt die Zusammenfassung (Score + Badge + Count) für eine Ernährungsform.
function ScoreCard({ title, rep }: { title: string; rep: ReportSingle }) {
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

// RulesList: Liste der (anwendbaren) Regeln, optional gefiltert auf fehlgeschlagene Regeln.
function RulesList({
  rep,
  onlyFailed,
}: {
  rep: ReportSingle;
  onlyFailed: boolean;
}) {
  const rules = rep.rules
    .filter((r) => r.applies)
    .filter((r) => (onlyFailed ? !r.passed : true));

  return (
    <div className='mt-2.5 grid gap-2.5'>
      {rules.map((r) => (
        <div
          key={r.id}
          className={
            'rounded-xl border border-slate-300 p-3 text-slate-900 ' +
            (r.passed ? 'bg-emerald-100' : 'bg-red-100')
          }
        >
          <div className='flex justify-between gap-2.5'>
            <div className='font-extrabold'>{r.label}</div>
            <div className='font-black'>{r.passed ? '✅' : '❌'}</div>
          </div>

          {(r.expected !== undefined || r.actual !== undefined) && (
            <div className='mt-1.5'>
              Erwartet: <b>{r.expected ?? '-'}</b> • Ist:{' '}
              <b>{r.actual ?? '-'}</b>
            </div>
          )}

          {r.notes && <div className='mt-1.5'>{r.notes}</div>}
        </div>
      ))}
    </div>
  );
}

// Page: Haupt-UI (Upload + Analyse + Ergebnisdarstellung) inkl. Light/Dark-Mode.
export default function Page() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const [dual, setDual] = useState<ReportDual | null>(null);

  // Hilfsfunktion: nimmt die erste Datei aus einem Drop-Event.
  function pickFirstFile(dt: DataTransfer | null): File | null {
    if (!dt) return null;
    const f = dt.files?.[0];
    return f ?? null;
  }

  // Entfernt die ausgewählte Datei und leert zusätzlich den versteckten File-Input.
  function clearSelectedFile() {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  // analyze(): sendet die Datei an /api/analyze und speichert den dual-Report im State.
  async function analyze() {
    setError(null);
    setDual(null);

    if (!file) {
      setError('Bitte eine Datei auswählen (.xlsx oder .json).');
      return;
    }

    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);

      const res = await fetch('/api/analyze', {
        method: 'POST',
        body: fd,
      });

      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `HTTP ${res.status}`);
      }

      const data = (await res.json()) as ReportDual;

      // Wir erwarten dual. Falls Backend mal single zurückgibt,
      // kann man hier später fallbacken. Für jetzt: dual nötig.
      if (!data || data.mode !== 'dual') {
        throw new Error(
          'Backend hat keinen dual-Report geliefert (erwarte mode="dual").'
        );
      }

      setDual(data as ReportDual);
    } catch (e: unknown) {
      if (e instanceof Error) {
        setError(e.message);
      } else {
        setError('Unbekannter Fehler');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className='min-h-screen w-screen box-border bg-white p-6 text-center font-sans text-slate-900'>
      <h1 className='m-0 text-[28px] font-black'>GENAU – Speiseplan Check</h1>
      <p className='mt-2 text-slate-600 opacity-80'>Upload Excel/JSON</p>

      <section className='mx-auto mt-5 grid w-full max-w-300 gap-3 rounded-xl border border-slate-200 bg-white p-4 text-slate-900'>
        <div className='mx-auto grid w-full max-w-205 justify-items-stretch gap-2'>
          <div className='font-extrabold'>Datei hochladen</div>

          {/* Versteckter nativer File-Input (Dialog) */}
          <input
            ref={fileInputRef}
            type='file'
            accept='.xlsx,.xls,.json'
            className='hidden'
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />

          {/* Drag & Drop Zone */}
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
              'relative grid min-h-35 w-full cursor-pointer select-none place-items-center rounded-xl border-2 border-dashed p-4.5 text-center ' +
              (isDragging
                ? 'border-slate-900 bg-slate-100'
                : 'border-slate-300 bg-slate-100')
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
                className='absolute right-2.5 top-2.5 grid h-7.5 w-7.5 place-items-center rounded-full border border-slate-300 bg-white text-slate-900 hover:bg-slate-50'
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
                  className='grid h-11 w-11 place-items-center rounded-full border border-slate-300 bg-white text-slate-900'
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

          <button
            onClick={analyze}
            disabled={loading}
            className='w-full rounded-[10px] border border-slate-900 bg-white px-3.5 py-2.5 font-extrabold text-slate-900 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60'
          >
            {loading ? 'Analysiere…' : 'Analysieren'}
          </button>

          {error && (
            <div className='whitespace-pre-wrap text-red-600'>{error}</div>
          )}
        </div>

        {dual && (
          <section className='mt-5.5 grid gap-4.5'>
            <div className='grid grid-cols-2 gap-3'>
              <ScoreCard title='Mischkost' rep={dual.mixed} />
              <ScoreCard title='Vegetarisch' rep={dual.ovo_lacto_vegetarian} />
            </div>

            <div className='grid grid-cols-2 gap-3'>
              <div>
                <h2 className='text-lg font-black'>Regeln – Mischkost</h2>
                <RulesList rep={dual.mixed} onlyFailed={false} />
              </div>

              <div>
                <h2 className='text-lg font-black'>Regeln – Vegetarisch</h2>
                <RulesList rep={dual.ovo_lacto_vegetarian} onlyFailed={false} />
              </div>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
