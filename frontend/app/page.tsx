'use client';

import React, { useMemo, useRef, useState } from 'react';
import { StepNavigation } from './components/navigation/StepNavigation';
import { ReportSection } from './components/report/ReportSection';
import { SelfCheckSection } from './components/selfcheck/SelfCheckSection';
import { UploadSection } from './components/upload/UploadSection';
import {
  toggleFoodGroup,
  toggleTag,
  type AnalyzeResponse,
  type FoodGroup,
  type PlanDoc,
  type PreviewResponse,
  type RelevantTag,
} from './lib/foodplan';

// Page steuert den kompletten Ablauf: Upload -> Report -> Selbstcheck.
// Die großen UI-Teile sind ausgelagert, hier bleibt vor allem State + Flow-Logik.
export default function Page() {
  // Datei- und Request-Zustände.
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Report-/Wochenzustände.
  const [reportData, setReportData] = useState<AnalyzeResponse | null>(null);
  const [activeWeekIndex, setActiveWeekIndex] = useState(0);
  const [selfCheckWeekIndex, setSelfCheckWeekIndex] = useState(0);

  // Preview und editierbarer Plan für den Selbstcheck.
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [planDraft, setPlanDraft] = useState<PlanDoc | null>(null);

  // Merkt, welche Menü-Akkordeons aktuell geöffnet sind.
  const [openMenus, setOpenMenus] = useState<Record<string, boolean>>({});

  type Step = 'upload' | 'report' | 'selfcheck';
  const [step, setStep] = useState<Step>('upload');

  // Entfernt die ausgewählte Datei und leert zusätzlich den versteckten File-Input.
  function clearSelectedFile() {
    setFile(null);
    setReportData(null);
    setPreview(null);
    setPlanDraft(null);
    setError(null);
    setActiveWeekIndex(0);
    setSelfCheckWeekIndex(0);
    setStep('upload');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function startSelfCheck() {
    // Initialisiert Preview und erzeugt direkt den ersten Report.
    setError(null);
    setReportData(null);
    setPreview(null);
    setPlanDraft(null);
    setActiveWeekIndex(0);
    setSelfCheckWeekIndex(0);

    if (!file) {
      setError('Bitte eine Datei auswählen (.xlsx).');
      return;
    }

    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);

      const res = await fetch('/api/preview', {
        method: 'POST',
        body: fd,
      });

      if (!res.ok) {
        const contentType = res.headers.get('content-type') ?? '';
        const msg = await res.text();

        // Flask kann bei abort(...) (oder durch Proxy/Hard-Error) statt JSON/Text auch HTML liefern.
        // Für Nutzer zeigen wir dann eine kurze Standardmeldung.
        // Für Debugging loggen wir Details in die Konsole (statt sie im UI anzuzeigen).
        const fallback =
          'Datei ist ungültig oder passt nicht zum Template.\n\nHäufige Ursachen:\n- falscher Tabellenblatt-Name (erwartet: "Tabelle1")\n- fehlende Wochentage in Spalte A (Montag–Freitag)\n- keine Gerichte in den vorgesehenen Spalten';

        const isProbablyHtml = contentType.includes('text/html');

        if (!msg || isProbablyHtml) {
          console.error('Preview upload failed', {
            status: res.status,
            contentType,
            bodySnippet: msg?.slice(0, 500) ?? '',
          });
        }

        const finalMsg = msg && !isProbablyHtml ? msg : fallback;

        throw new Error(finalMsg || `HTTP ${res.status}`);
      }

      const data = (await res.json()) as PreviewResponse;
      if (!data || data.mode !== 'preview' || !data.plan) {
        throw new Error('Backend hat keinen Preview-Plan geliefert.');
      }

      setPreview(data);
      setPlanDraft(structuredClone(data.plan));

      // Direkt einen ersten Report berechnen und anzeigen.
      const analyzeRes = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: data.plan }),
      });

      if (!analyzeRes.ok) {
        const msg = await analyzeRes.text();
        throw new Error(msg || `HTTP ${analyzeRes.status}`);
      }

      const report = (await analyzeRes.json()) as AnalyzeResponse;
      if (
        !report ||
        (report.mode !== 'dual' && report.mode !== 'monthly_dual')
      ) {
        throw new Error(
          'Backend hat keinen Report geliefert (erwarte mode="dual" oder "monthly_dual").',
        );
      }

      setReportData(report);
      setStep('report');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unbekannter Fehler');
    } finally {
      setLoading(false);
    }
  }

  async function analyzeCorrectedPlan() {
    // Rechnet den Report auf Basis der im Selbstcheck bearbeiteten Daten neu.
    setError(null);
    setReportData(null);

    if (!planDraft) {
      setError('Kein Plan zum Auswerten vorhanden. Erst Selbstcheck starten.');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: planDraft }),
      });

      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `HTTP ${res.status}`);
      }

      const data = (await res.json()) as AnalyzeResponse;
      if (!data || (data.mode !== 'dual' && data.mode !== 'monthly_dual')) {
        throw new Error(
          'Backend hat keinen Report geliefert (erwarte mode="dual" oder "monthly_dual").',
        );
      }

      setReportData(data);
      setStep('report');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unbekannter Fehler');
    } finally {
      setLoading(false);
    }
  }

  const draftItemCount = useMemo(() => {
    // Kennzahl für den Selbstcheck-Header.
    const days = planDraft?.days ?? [];
    let n = 0;
    for (const d of days) {
      for (const m of d.menus ?? []) {
        n += (m.items ?? []).length;
      }
    }
    return n;
  }, [planDraft]);

  // Anzahl Items ohne erkannte Gruppe (über den ganzen Plan)
  const missingFoodGroupCount = useMemo(() => {
    const days = planDraft?.days ?? [];
    let n = 0;
    for (const d of days) {
      for (const m of d.menus ?? []) {
        for (const it of m.items ?? []) {
          const hasGroup =
            (Array.isArray(it.food_groups) && it.food_groups.length > 0) ||
            Boolean(it.links?.food_group);
          if (!hasGroup) n += 1;
        }
      }
    }
    return n;
  }, [planDraft]);

  const selfCheckWeeks = useMemo(() => {
    // Baut die verfügbare Wochenliste aus den Tagesdaten auf.
    const days = planDraft?.days ?? [];
    const byWeek = new Map<number, string>();

    for (const d of days) {
      const idx = d.week_index ?? 0;
      if (!byWeek.has(idx)) {
        byWeek.set(idx, d.week_label || `Woche ${idx + 1}`);
      }
    }

    if (byWeek.size === 0) {
      byWeek.set(0, 'Woche 1');
    }

    return Array.from(byWeek.entries())
      .map(([week_index, week_label]) => ({ week_index, week_label }))
      .sort((a, b) => a.week_index - b.week_index);
  }, [planDraft]);

  const missingFoodGroupByWeek = useMemo(() => {
    // Zählt fehlende Zuordnungen pro Woche für Warnindikatoren.
    const days = planDraft?.days ?? [];
    const counts = new Map<number, number>();

    for (const d of days) {
      const weekIdx = d.week_index ?? 0;
      let weekMissing = counts.get(weekIdx) ?? 0;

      for (const m of d.menus ?? []) {
        for (const it of m.items ?? []) {
          const hasGroup =
            (Array.isArray(it.food_groups) && it.food_groups.length > 0) ||
            Boolean(it.links?.food_group);
          if (!hasGroup) weekMissing += 1;
        }
      }

      counts.set(weekIdx, weekMissing);
    }

    return counts;
  }, [planDraft]);

  const normalizedSelfCheckWeekIndex = useMemo(() => {
    // Fallback, falls die aktuell gewählte Woche nicht mehr verfügbar ist.
    const weekIndices = new Set(selfCheckWeeks.map((w) => w.week_index));
    if (weekIndices.has(selfCheckWeekIndex)) return selfCheckWeekIndex;
    return selfCheckWeeks[0]?.week_index ?? 0;
  }, [selfCheckWeekIndex, selfCheckWeeks]);

  const selfCheckDays = useMemo(() => {
    // Filtert im Selbstcheck auf die aktive Woche.
    const days = planDraft?.days ?? [];
    return days
      .map((day, dayIdx) => ({ day, dayIdx }))
      .filter(
        ({ day }) => (day.week_index ?? 0) === normalizedSelfCheckWeekIndex,
      );
  }, [planDraft, normalizedSelfCheckWeekIndex]);

  function toggleItemFoodGroup(
    dayIdx: number,
    menuIdx: number,
    itemIdx: number,
    fg: Exclude<FoodGroup, ''>,
  ) {
    setPlanDraft((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      const item = next.days?.[dayIdx]?.menus?.[menuIdx]?.items?.[itemIdx];
      if (!item) return prev;

      // Wenn noch keine Multi-Liste existiert, aber eine Single-Group gesetzt ist,
      // übernehmen wir sie als Startwert, damit sie beim Hinzufügen nicht „verschwindet“.
      if (!Array.isArray(item.food_groups) || item.food_groups.length === 0) {
        const single = item.links?.food_group;
        item.food_groups = single ? [single] : [];
      }

      item.food_groups = toggleFoodGroup(item.food_groups, fg);

      // Für ältere Backend-Logik/Kompatibilität weiterhin pflegen (Primary = erstes Element)
      item.links = item.links ?? {};
      item.links.food_group = item.food_groups[0] ?? null;

      return next;
    });
  }

  function toggleItemTag(
    dayIdx: number,
    menuIdx: number,
    itemIdx: number,
    tag: RelevantTag,
  ) {
    setPlanDraft((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      const item = next.days?.[dayIdx]?.menus?.[menuIdx]?.items?.[itemIdx];
      if (!item) return prev;
      item.tags = toggleTag(item.tags, tag);
      return next;
    });
  }

  return (
    <main className='min-h-screen w-screen box-border bg-slate-50 p-6 text-center font-sans text-slate-900'>
      <h1 className='m-0 text-[28px] font-black'>GENAU – Speiseplan Check</h1>

      <section className='mx-auto mt-5 grid w-full max-w-300 gap-3 rounded-xl border border-slate-200 bg-white p-4 text-slate-900'>
        {/* Step indicator + Navigation */}
        {step !== 'selfcheck' && (
          <StepNavigation
            step={step}
            loading={loading}
            onBack={() => {
              setError(null);
              if (step === 'report') setStep('upload');
            }}
            onNext={() => {
              setError(null);
              if (step === 'upload') {
                void startSelfCheck();
                return;
              }
              setSelfCheckWeekIndex(activeWeekIndex);
              setStep('selfcheck');
            }}
          />
        )}

        {error && (
          <div
            role='alert'
            aria-live='assertive'
            className='rounded-xl border border-red-200 bg-red-50 p-3 text-left text-red-900'
          >
            <div className='flex items-start gap-2'>
              <span className='text-base font-black'>⚠️</span>
              <div>
                <div className='text-sm font-extrabold'>
                  Upload fehlgeschlagen
                </div>
                <div className='mt-1 text-xs text-red-800'>
                  Bitte Datei/Format prüfen und erneut versuchen.
                </div>

                <div className='mt-2 space-y-1'>
                  {error
                    .split('\n')
                    .map((line) => line.trim())
                    .filter(Boolean)
                    .map((line, idx) => (
                      <div
                        key={idx}
                        className='text-sm leading-snug text-red-900'
                      >
                        {line.startsWith('-') ? line : `• ${line}`}
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 1: UPLOAD */}
        {step === 'upload' && (
          <UploadSection
            file={file}
            isDragging={isDragging}
            fileInputRef={fileInputRef}
            setFile={setFile}
            setIsDragging={setIsDragging}
            clearSelectedFile={clearSelectedFile}
          />
        )}

        {/* STEP 2: SELBSTCHECK */}
        {step === 'selfcheck' && preview && planDraft && (
          <SelfCheckSection
            draftItemCount={draftItemCount}
            selfCheckWeeks={selfCheckWeeks}
            missingFoodGroupByWeek={missingFoodGroupByWeek}
            normalizedSelfCheckWeekIndex={normalizedSelfCheckWeekIndex}
            setSelfCheckWeekIndex={setSelfCheckWeekIndex}
            selfCheckDays={selfCheckDays}
            openMenus={openMenus}
            setOpenMenus={setOpenMenus}
            toggleItemFoodGroup={toggleItemFoodGroup}
            toggleItemTag={toggleItemTag}
            loading={loading}
            onBackToReport={() => {
              setError(null);
              setStep('report');
            }}
            onAnalyze={analyzeCorrectedPlan}
          />
        )}

        {/* STEP 3: REPORT */}
        {step === 'report' && reportData && (
          <ReportSection
            reportData={reportData}
            loading={loading}
            missingFoodGroupCount={missingFoodGroupCount}
            activeWeekIndex={activeWeekIndex}
            setActiveWeekIndex={setActiveWeekIndex}
            onGoToSelfcheck={() => {
              setError(null);
              setStep('selfcheck');
            }}
          />
        )}
      </section>
    </main>
  );
}
