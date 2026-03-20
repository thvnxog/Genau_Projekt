'use client';

import React, { useMemo, useRef, useState } from 'react';

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

// --- Self-check types -------------------------------------------------

type PlanItem = {
  raw_text?: string;
  links?: { food_group?: string | null };
  // Tags sind im Selbstcheck editierbar (optional), weil sie Regel-Ausnahmen/Verfeinerungen abbilden.
  tags?: string[];
  // Optional: Mehrfach-Zuordnung von Food-Groups (für Selbstcheck-UI / Auswertung)
  food_groups?: string[];
};

type PlanMenu = {
  menu_type?: string;
  items?: PlanItem[];
};

type PlanDay = {
  weekday?: string;
  menus?: PlanMenu[];
};

type PlanDoc = {
  schema_version?: string;
  days?: PlanDay[];
};

type PreviewResponse = {
  schema_version?: string;
  mode: 'preview';
  plan: PlanDoc;
  stats?: Record<string, unknown>;
};

const FOOD_GROUPS = [
  '',
  'grains_potatoes',
  'vegetables',
  'legumes',
  'fruit',
  'dairy',
  'meat',
  'fish',
] as const;

type FoodGroup = (typeof FOOD_GROUPS)[number];

const FOOD_GROUP_LABELS: Record<Exclude<FoodGroup, ''>, string> = {
  grains_potatoes: 'Getreide / Kartoffeln',
  vegetables: 'Gemüse / Salat',
  legumes: 'Hülsenfrüchte',
  fruit: 'Obst',
  dairy: 'Milch / Milchprodukte',
  meat: 'Fleisch / Wurst',
  fish: 'Fisch',
};

const RELEVANT_TAGS = [
  'wholegrain',
  'potato_product',
  'raw_veg',
  'whole_fruit',
] as const;

type RelevantTag = (typeof RELEVANT_TAGS)[number];

const TAG_LABELS: Record<RelevantTag, string> = {
  wholegrain: 'Vollkorn',
  potato_product: 'Kartoffelerzeugnis (z. B. Püree, Kroketten, Pommes)',
  raw_veg: 'Rohkost (ungegart)',
  whole_fruit: 'Stückobst (kein Mus/Saft)',
};

// Styling für Food Groups (Icon + Farbe)
const FOOD_GROUP_STYLES: Record<
  Exclude<FoodGroup, ''>,
  { icon: string; color: string; bg: string }
> = {
  grains_potatoes: { icon: '🌾', color: '#b45309', bg: '#fef3c7' },
  vegetables: { icon: '🥦', color: '#15803d', bg: '#dcfce7' },
  legumes: { icon: '🫘', color: '#7c2d12', bg: '#fed7aa' },
  fruit: { icon: '🍎', color: '#991b1b', bg: '#fee2e2' },
  dairy: { icon: '🥛', color: '#0c4a6e', bg: '#e0f2fe' },
  meat: { icon: '🍖', color: '#7c2d12', bg: '#ffedd5' },
  fish: { icon: '🐟', color: '#164e63', bg: '#cffafe' },
};

function toggleTag(list: string[] | undefined, tag: RelevantTag): string[] {
  const tags = Array.isArray(list) ? [...list] : [];
  if (tags.includes(tag)) return tags.filter((t) => t !== tag);
  tags.push(tag);
  return tags;
}

function toggleFoodGroup(
  list: string[] | undefined,
  fg: Exclude<FoodGroup, ''>,
): string[] {
  const groups = Array.isArray(list) ? [...list] : [];
  if (groups.includes(fg)) return groups.filter((g) => g !== fg);
  groups.push(fg);
  return groups;
}

function getPrimaryFoodGroup(item: PlanItem): string {
  // Legacy-Helfer fürs UI: liefert eine einzelne "Hauptgruppe" zum Anzeigen.
  // Für die Auswertung werden alle Einträge in `item.food_groups[]` gezählt (falls vorhanden).
  // Fallback bleibt `links.food_group`.
  const fromMulti = Array.isArray(item.food_groups)
    ? item.food_groups[0]
    : undefined;
  return (fromMulti ?? item.links?.food_group ?? '') as string;
}

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

// Page: Haupt-UI (Upload + Analyse + Ergebnisdarstellung) inkl. Light/Dark-Mode.
export default function Page() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const [dual, setDual] = useState<ReportDual | null>(null);

  // NEU: Self-check state
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [planDraft, setPlanDraft] = useState<PlanDoc | null>(null);

  // UI: standardmäßig nur Problemfälle zeigen
  const [showAllSelfCheckFields, setShowAllSelfCheckFields] = useState(false);

  // NEU: pro Menü können wir „alles anzeigen“ aktivieren, indem das Menü geöffnet wird.
  const [openMenus, setOpenMenus] = useState<Record<string, boolean>>({});

  type Step = 'upload' | 'report' | 'selfcheck';
  const [step, setStep] = useState<Step>('upload');

  // Hilfsfunktion: nimmt die erste Datei aus einem Drop-Event.
  function pickFirstFile(dt: DataTransfer | null): File | null {
    if (!dt) return null;
    const f = dt.files?.[0];
    return f ?? null;
  }

  // Entfernt die ausgewählte Datei und leert zusätzlich den versteckten File-Input.
  function clearSelectedFile() {
    setFile(null);
    setDual(null);
    setPreview(null);
    setPlanDraft(null);
    setError(null);
    setStep('upload');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function startSelfCheck() {
    setError(null);
    setDual(null);
    setPreview(null);
    setPlanDraft(null);

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

      const report = (await analyzeRes.json()) as ReportDual;
      if (!report || report.mode !== 'dual') {
        throw new Error(
          'Backend hat keinen dual-Report geliefert (erwarte mode="dual").',
        );
      }

      setDual(report);
      setStep('report');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unbekannter Fehler');
    } finally {
      setLoading(false);
    }
  }

  async function analyzeCorrectedPlan() {
    setError(null);
    setDual(null);

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

      const data = (await res.json()) as ReportDual;
      if (!data || data.mode !== 'dual') {
        throw new Error(
          'Backend hat keinen dual-Report geliefert (erwarte mode="dual").',
        );
      }

      setDual(data);
      setStep('report');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unbekannter Fehler');
    } finally {
      setLoading(false);
    }
  }

  const draftItemCount = useMemo(() => {
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
    <main className='min-h-screen w-screen box-border bg-white p-6 text-center font-sans text-slate-900'>
      <h1 className='m-0 text-[28px] font-black'>GENAU – Speiseplan Check</h1>

      <section className='mx-auto mt-5 grid w-full max-w-300 gap-3 rounded-xl border border-slate-200 bg-white p-4 text-slate-900'>
        {/* Step indicator + Navigation */}
        {step !== 'selfcheck' && (
          <div className='flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-left'>
            <div className='text-sm font-extrabold'>
              Schritt:{' '}
              <span className='font-black'>
                {step === 'upload' ? '1/3 Upload' : '2/3 Report'}
              </span>
            </div>

            <div className='flex flex-wrap gap-2'>
              <button
                type='button'
                className='cursor-pointer rounded-[10px] border border-slate-300 bg-white px-3 py-2 text-sm font-extrabold text-slate-900 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60'
                disabled={step === 'upload' || loading}
                onClick={() => {
                  setError(null);
                  if (step === 'report') setStep('upload');
                }}
              >
                Zurück
              </button>

              <button
                type='button'
                className='cursor-pointer rounded-[10px] border border-slate-900 bg-slate-900 px-3 py-2 text-sm font-extrabold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60'
                disabled={loading}
                onClick={async () => {
                  setError(null);
                  if (step === 'upload') return startSelfCheck();
                  if (step === 'report') setStep('selfcheck');
                }}
              >
                {loading
                  ? 'Lade…'
                  : step === 'upload'
                    ? 'Weiter'
                    : 'Weiter zum Selbstcheck'}
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className='whitespace-pre-wrap text-left text-red-600'>
            {error}
          </div>
        )}

        {/* STEP 1: UPLOAD */}
        {step === 'upload' && (
          <div className='mx-auto grid w-full max-w-205 justify-items-stretch gap-2'>
            <div className='font-extrabold'>Datei hochladen</div>

            <input
              ref={fileInputRef}
              type='file'
              accept='.xlsx'
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
                  className='absolute right-2.5 top-2.5 grid h-7.5 w-7.5 cursor-pointer place-items-center rounded-full border border-slate-300 bg-white text-slate-900 hover:bg-slate-50'
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

            <div className='text-left text-xs text-slate-600'>
              Vorlage nötig?{' '}
              <a
                href='/Speiseplan_Template.xlsx'
                download
                className='font-bold text-slate-900 underline underline-offset-2'
              >
                Template herunterladen
              </a>
              .
            </div>
          </div>
        )}

        {/* STEP 2: SELBSTCHECK */}
        {step === 'selfcheck' && preview && planDraft && (
          <section className='grid gap-4.5 text-left'>
            <div className='rounded-xl border border-slate-200 bg-slate-50 p-3.5'>
              <div className='font-black'>Lebensmittelgruppen prüfen</div>
              <div className='mt-1 text-sm text-slate-700'>
                Standardmäßig werden nur Gerichte angezeigt, bei denen keine
                Gruppe erkannt wurde.
              </div>
              <div className='mt-2 text-xs text-slate-600'>
                Items im Plan: <b>{draftItemCount}</b>
              </div>

              <label className='mt-3 flex items-center gap-2 text-sm font-bold text-slate-700'>
                <input
                  type='checkbox'
                  className='cursor-pointer'
                  checked={showAllSelfCheckFields}
                  onChange={(e) => setShowAllSelfCheckFields(e.target.checked)}
                />
                Alle Felder anzeigen
              </label>
            </div>

            <div className='grid gap-3'>
              {(planDraft.days ?? []).map((day, dayIdx) => (
                <div
                  key={dayIdx}
                  className='rounded-xl border border-slate-200 bg-white p-3.5'
                >
                  <div className='font-black'>
                    {day.weekday ?? `Tag ${dayIdx + 1}`}
                  </div>

                  <div className='mt-2 grid gap-3'>
                    {(day.menus ?? []).map((menu, menuIdx) => {
                      const missingCount = (menu.items ?? []).filter(
                        (it) => !it.links?.food_group,
                      ).length;

                      const menuKey = `${dayIdx}-${menuIdx}`;
                      const isMenuOpen = openMenus[menuKey] ?? missingCount > 0;

                      // Wenn im Menü alles erkannt ist, zeigen wir statt „0 ohne Gruppe“
                      // eine kurze Übersicht, welche Gruppen vorkommen.
                      const recognizedGroups = Array.from(
                        new Set(
                          (menu.items ?? [])
                            .map((it) => getPrimaryFoodGroup(it))
                            .filter(Boolean),
                        ),
                      ) as Exclude<FoodGroup, ''>[];

                      const recognizedGroupsLabel = recognizedGroups
                        .map((g) => FOOD_GROUP_LABELS[g])
                        .join(' · ');

                      // „Alle Felder“ gilt entweder global oder für dieses eine geöffnete Menü.
                      const showAllForMenu =
                        showAllSelfCheckFields || isMenuOpen;

                      return (
                        <details
                          key={menuKey}
                          open={isMenuOpen}
                          onToggle={(e) => {
                            const el = e.currentTarget;
                            setOpenMenus((prev) => ({
                              ...prev,
                              [menuKey]: el.open,
                            }));
                          }}
                          className='rounded-lg border border-slate-100 bg-slate-50 p-3'
                        >
                          <summary className='cursor-pointer select-none text-sm font-extrabold'>
                            Menü: {menu.menu_type}{' '}
                            {missingCount > 0 ? (
                              <span className='ml-2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-black text-slate-700'>
                                {missingCount} ohne Gruppe
                              </span>
                            ) : (
                              recognizedGroupsLabel && (
                                <span className='ml-2 text-xs font-bold text-slate-600'>
                                  Erkannt: {recognizedGroupsLabel}
                                </span>
                              )
                            )}
                          </summary>

                          <div className='mt-2 grid gap-2'>
                            {(menu.items ?? [])
                              .map((it, itemIdx) => ({ it, itemIdx }))
                              .filter(({ it }) =>
                                showAllForMenu ? true : !it.links?.food_group,
                              )
                              .map(({ it, itemIdx }) => {
                                const recognizedGroup = Boolean(
                                  it.links?.food_group,
                                );
                                const showGroups =
                                  showAllForMenu || !recognizedGroup;

                                if (!showGroups) return null;

                                return (
                                  <details
                                    key={itemIdx}
                                    className='rounded-lg border border-slate-200 bg-white'
                                  >
                                    <summary className='cursor-pointer select-none p-2.5 text-sm font-bold flex items-center gap-2'>
                                      <span>
                                        {recognizedGroup ? '✓' : '⚠️'}
                                      </span>
                                      {it.raw_text}
                                    </summary>

                                    <div className='border-t border-slate-200 p-3 space-y-4'>
                                      {/* Food Groups Section */}
                                      <div>
                                        <div className='text-xs font-bold text-slate-700 mb-2'>
                                          Lebensmittelgruppen
                                        </div>
                                        <div className='text-[11px] font-normal text-slate-600 mb-3'>
                                          Wähle alle zutreffenden Gruppen aus.
                                        </div>

                                        <div className='flex flex-wrap gap-2'>
                                          {(
                                            FOOD_GROUPS.filter(
                                              Boolean,
                                            ) as Exclude<FoodGroup, ''>[]
                                          ).map((g) => {
                                            const isSelected = (
                                              it.food_groups ??
                                              [it.links?.food_group].filter(
                                                Boolean,
                                              )
                                            ).includes(g);
                                            const style = FOOD_GROUP_STYLES[g];

                                            return (
                                              <button
                                                key={g}
                                                type='button'
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  toggleItemFoodGroup(
                                                    dayIdx,
                                                    menuIdx,
                                                    itemIdx,
                                                    g,
                                                  );
                                                }}
                                                className={`cursor-pointer rounded-full px-3 py-1.5 text-xs font-semibold transition-all ${
                                                  isSelected
                                                    ? 'ring-2 ring-offset-1 ring-slate-400'
                                                    : 'opacity-70 hover:opacity-100'
                                                }`}
                                                style={{
                                                  backgroundColor: style.bg,
                                                  color: style.color,
                                                }}
                                              >
                                                <span className='mr-1'>
                                                  {style.icon}
                                                </span>
                                                {FOOD_GROUP_LABELS[g]}
                                              </button>
                                            );
                                          })}
                                        </div>
                                      </div>

                                      {/* Tags Section (Collapsible) */}
                                      <details className='group'>
                                        <summary className='cursor-pointer select-none text-xs font-bold text-slate-700 flex items-center gap-2 hover:text-slate-900'>
                                          <span className='transition-transform group-open:rotate-90'>
                                            ▶
                                          </span>
                                          Zusätze / Tags (optional)
                                        </summary>

                                        <div className='mt-3 space-y-2 pl-4 border-l-2 border-slate-200'>
                                          <div className='text-[11px] font-normal text-slate-600'>
                                            Falls im Speiseplan nicht eindeutig
                                            erkennbar.
                                          </div>

                                          <div className='flex flex-wrap gap-2'>
                                            {(
                                              RELEVANT_TAGS as readonly RelevantTag[]
                                            ).map((t) => {
                                              const isSelected = (
                                                it.tags ?? []
                                              ).includes(t);

                                              return (
                                                <button
                                                  key={t}
                                                  type='button'
                                                  onClick={(e) => {
                                                    e.stopPropagation();
                                                    toggleItemTag(
                                                      dayIdx,
                                                      menuIdx,
                                                      itemIdx,
                                                      t,
                                                    );
                                                  }}
                                                  className={`cursor-pointer rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                                                    isSelected
                                                      ? 'bg-indigo-600 text-white'
                                                      : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
                                                  }`}
                                                >
                                                  {TAG_LABELS[t]}
                                                </button>
                                              );
                                            })}
                                          </div>
                                        </div>
                                      </details>

                                      {/* Summary */}
                                      <div className='mt-2 text-[11px] text-slate-500 pt-2 border-t border-slate-100'>
                                        Gruppen (für Auswertung):{' '}
                                        <b>
                                          {(() => {
                                            const list = (it.food_groups ??
                                              [it.links?.food_group].filter(
                                                Boolean,
                                              )) as Exclude<FoodGroup, ''>[];

                                            if (!list.length) return '—';

                                            return list
                                              .map((g) => FOOD_GROUP_LABELS[g])
                                              .join(' · ');
                                          })()}
                                        </b>
                                      </div>
                                    </div>
                                  </details>
                                );
                              })}

                            {!showAllSelfCheckFields && missingCount === 0 && (
                              <div className='text-xs text-slate-500'>
                                In diesem Menü wurde überall eine Gruppe
                                erkannt. (Bei Bedarf oben „Alle Felder anzeigen“
                                aktivieren.)
                              </div>
                            )}
                          </div>
                        </details>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            {/* Sticky Action Bar (damit kein Hochscrollen nötig ist) */}
            <div className='sticky bottom-0 z-10 -mx-4 mt-2 border-t border-slate-200 bg-white/90 p-3 backdrop-blur'>
              <div className='flex flex-wrap items-center justify-between gap-2'>
                <div className='text-xs text-slate-600'>
                  Schritt 3/3 – Selbstcheck
                </div>

                <div className='flex flex-wrap gap-2'>
                  <button
                    type='button'
                    className='cursor-pointer rounded-[10px] border border-slate-300 bg-white px-3 py-2 text-sm font-extrabold text-slate-900 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60'
                    disabled={loading}
                    onClick={() => {
                      setError(null);
                      setStep('report');
                    }}
                  >
                    Zurück zum Report
                  </button>

                  <button
                    type='button'
                    className='cursor-pointer rounded-[10px] border border-slate-900 bg-slate-900 px-3.5 py-2 text-sm font-extrabold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60'
                    disabled={loading}
                    onClick={analyzeCorrectedPlan}
                  >
                    {loading ? 'Berechne…' : 'Report aktualisieren'}
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* STEP 3: REPORT */}
        {step === 'report' && dual && (
          <section className='grid gap-4.5'>
            {missingFoodGroupCount > 0 && (
              <details className='rounded-xl border border-amber-200 bg-amber-50 p-3 text-left text-slate-900'>
                <summary className='cursor-pointer select-none font-extrabold flex items-center gap-2'>
                  <span className='text-lg'>⚠️</span>
                  <span>
                    Hinweis – {missingFoodGroupCount} Gerichte ohne Zuordnung
                  </span>
                </summary>

                <div className='mt-3 text-sm text-slate-700'>
                  <div className='mb-2'>
                    Für diese {missingFoodGroupCount} Gerichte konnte keine
                    passende Food-Group erkannt werden. Du kannst die
                    Zuordnungen im Selbstcheck ergänzen und den Report danach
                    neu berechnen.
                  </div>

                  <button
                    type='button'
                    className='cursor-pointer rounded-[10px] border border-slate-900 bg-slate-900 px-3 py-2 text-sm font-extrabold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60'
                    disabled={loading}
                    onClick={() => {
                      setError(null);
                      setStep('selfcheck');
                    }}
                  >
                    Jetzt überarbeiten
                  </button>
                </div>
              </details>
            )}

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
