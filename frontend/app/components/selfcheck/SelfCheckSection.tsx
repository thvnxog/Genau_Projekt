import React from 'react';
import { LoadingSpinner } from '../ui/LoadingSpinner';

import {
  FOOD_GROUP_LABELS,
  FOOD_GROUP_STYLES,
  FOOD_GROUPS,
  RELEVANT_TAGS,
  TAG_LABELS,
  getPrimaryFoodGroup,
  type FoodGroup,
  type PlanDay,
  type RelevantTag,
} from '../../lib/foodplan';

// Selbstcheck-UI: Zuordnungen prüfen, korrigieren und erneut auswerten.
type SelfCheckWeek = {
  week_index: number;
  week_label: string;
};

type SelfCheckSectionProps = {
  draftItemCount: number;
  selfCheckWeeks: SelfCheckWeek[];
  missingFoodGroupByWeek: Map<number, number>;
  normalizedSelfCheckWeekIndex: number;
  setSelfCheckWeekIndex: (weekIndex: number) => void;
  selfCheckDays: Array<{ day: PlanDay; dayIdx: number }>;
  openMenus: Record<string, boolean>;
  setOpenMenus: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  toggleItemFoodGroup: (
    dayIdx: number,
    menuIdx: number,
    itemIdx: number,
    fg: Exclude<FoodGroup, ''>,
  ) => void;
  toggleItemTag: (
    dayIdx: number,
    menuIdx: number,
    itemIdx: number,
    tag: RelevantTag,
  ) => void;
  loading: boolean;
  onBackToReport: () => void;
  onAnalyze: () => void;
};

export function SelfCheckSection({
  draftItemCount,
  selfCheckWeeks,
  missingFoodGroupByWeek,
  normalizedSelfCheckWeekIndex,
  setSelfCheckWeekIndex,
  selfCheckDays,
  openMenus,
  setOpenMenus,
  toggleItemFoodGroup,
  toggleItemTag,
  loading,
  onBackToReport,
  onAnalyze,
}: SelfCheckSectionProps) {
  return (
    <section className='grid gap-4.5 text-left'>
      {/* Kopfbereich mit Kontext und Wochenauswahl (bei Monatsplänen). */}
      <div className='rounded-xl border border-slate-200 bg-slate-50 p-3.5'>
        <div className='font-black'>Lebensmittelgruppen prüfen</div>
        <div className='mt-1 text-sm text-slate-800'>
          Standardmäßig werden nur Gerichte angezeigt, bei denen keine Gruppe
          erkannt wurde.
        </div>
        <div className='mt-2 text-xs text-slate-700'>
          Items im Plan: <b>{draftItemCount}</b>
        </div>

        {selfCheckWeeks.length > 1 && (
          <div className='mt-3'>
            <div className='mb-1 text-xs font-bold text-slate-700'>
              Woche auswählen
            </div>
            <div className='flex flex-wrap justify-center gap-2'>
              {selfCheckWeeks.map((w) => {
                const weekMissing =
                  missingFoodGroupByWeek.get(w.week_index) ?? 0;
                const hasMissing = weekMissing > 0;

                return (
                  <button
                    key={w.week_index}
                    type='button'
                    onClick={() => setSelfCheckWeekIndex(w.week_index)}
                    className={`cursor-pointer rounded-full border px-3 py-1 text-xs font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 ${
                      w.week_index === normalizedSelfCheckWeekIndex
                        ? 'border-teal-700 bg-teal-700 text-white'
                        : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-50'
                    }`}
                    title={
                      hasMissing
                        ? `${weekMissing} Einträge ohne Gruppe in dieser Woche`
                        : 'Alle Einträge dieser Woche haben eine Gruppe'
                    }
                  >
                    {hasMissing ? '⚠️ ' : ''}
                    {w.week_label || `Woche ${w.week_index + 1}`}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Tages-/Menülisten mit editierbaren Gruppen und optionalen Tags. */}
      <div className='grid gap-3'>
        {selfCheckDays.map(({ day, dayIdx }) => (
          <div
            key={dayIdx}
            className='rounded-xl border border-slate-200 bg-white/95 p-3.5 shadow-sm'
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
                const isMenuOpen = openMenus[menuKey] ?? false;

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

                const showAllForMenu = isMenuOpen;

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
                    <summary className='cursor-pointer select-none rounded text-sm font-extrabold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'>
                      Menü: {menu.menu_type}{' '}
                      {missingCount > 0 ? (
                        <span className='ml-2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-black text-slate-700'>
                          ⚠️ {missingCount} ohne Gruppe
                        </span>
                      ) : (
                        recognizedGroupsLabel && (
                          <span className='ml-2 text-xs font-bold text-slate-700'>
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
                          const recognizedGroup = Boolean(it.links?.food_group);
                          const showGroups = showAllForMenu || !recognizedGroup;

                          if (!showGroups) return null;

                          return (
                            <details
                              key={itemIdx}
                              className='rounded-lg border border-slate-200 bg-white'
                            >
                              <summary className='cursor-pointer select-none rounded p-2.5 text-sm font-bold flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'>
                                <span>{recognizedGroup ? '✓' : '⚠️'}</span>
                                {it.raw_text}
                              </summary>

                              <div className='border-t border-slate-200 p-3 space-y-4'>
                                <div>
                                  <div className='text-xs font-bold text-slate-700 mb-2'>
                                    Lebensmittelgruppen
                                  </div>
                                  <div className='text-[11px] font-normal text-slate-700 mb-3'>
                                    Wähle alle zutreffenden Gruppen aus.
                                  </div>

                                  <div className='flex flex-wrap gap-2'>
                                    {(
                                      FOOD_GROUPS.filter(Boolean) as Exclude<
                                        FoodGroup,
                                        ''
                                      >[]
                                    ).map((g) => {
                                      const isSelected = (
                                        it.food_groups ??
                                        [it.links?.food_group].filter(Boolean)
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

                                <details className='group'>
                                  <summary className='cursor-pointer select-none rounded text-xs font-bold text-slate-800 flex items-center gap-2 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2'>
                                    <span className='transition-transform group-open:rotate-90'>
                                      ▶
                                    </span>
                                    Zusätze / Tags (optional)
                                  </summary>

                                  <div className='mt-3 space-y-2 pl-4 border-l-2 border-slate-200'>
                                    <div className='text-[11px] font-normal text-slate-700'>
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

                                <div className='mt-2 text-[11px] text-slate-600 pt-2 border-t border-slate-100'>
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

                      {missingCount === 0 && (
                        <div className='text-xs text-slate-600'>
                          In diesem Menü wurde überall eine Gruppe erkannt.
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

      {/* Sticky-Leiste für schnelles Zurückspringen und Neu-Berechnen. */}
      <div className='sticky bottom-0 z-10 -mx-4 mt-2 border-t border-slate-200 bg-white/90 p-3 backdrop-blur'>
        <div className='flex flex-wrap items-center justify-between gap-2'>
          <div className='text-xs text-slate-600'>
            Schritt 3/3 – Selbstcheck
          </div>

          <div className='flex flex-wrap gap-2'>
            <button
              type='button'
              className='cursor-pointer rounded-[10px] border border-slate-300 bg-white px-3 py-2 text-sm font-extrabold text-slate-900 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'
              disabled={loading}
              onClick={onBackToReport}
            >
              Zurück zum Report
            </button>

            <button
              type='button'
              className='cursor-pointer rounded-[10px] border border-teal-700 bg-teal-700 px-3.5 py-2 text-sm font-extrabold text-white hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60'
              disabled={loading}
              onClick={onAnalyze}
            >
              {loading ? (
                <span className='inline-flex items-center gap-2'>
                  <LoadingSpinner className='text-white' />
                  Berechne...
                </span>
              ) : (
                'Report aktualisieren'
              )}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
