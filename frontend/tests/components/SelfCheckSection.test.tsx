import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { SelfCheckSection } from '../../app/components/selfcheck/SelfCheckSection';

const day = {
  weekday: 'Montag',
  week_index: 0,
  week_label: 'Woche 1',
  menus: [
    {
      menu_type: 'mischkost',
      items: [
        {
          raw_text: 'Gemüsepfanne',
          links: { food_group: null },
          food_groups: [],
          tags: [],
        },
      ],
    },
  ],
};

test('selfcheck section exposes group chips and update action', () => {
  // Im Selbstcheck werden Lebensmittelgruppen manuell ausgewählt und anschließend neu berechnet.
  const toggleItemFoodGroup = vi.fn();
  const toggleItemTag = vi.fn();
  const setOpenMenus = vi.fn();
  const setSelfCheckWeekIndex = vi.fn();
  const onAnalyze = vi.fn();

  render(
    <SelfCheckSection
      draftItemCount={1}
      selfCheckWeeks={[{ week_index: 0, week_label: 'Woche 1' }]}
      missingFoodGroupByWeek={new Map([[0, 1]])}
      normalizedSelfCheckWeekIndex={0}
      setSelfCheckWeekIndex={setSelfCheckWeekIndex}
      selfCheckDays={[{ day, dayIdx: 0 }]}
      openMenus={{}}
      setOpenMenus={setOpenMenus}
      toggleItemFoodGroup={toggleItemFoodGroup}
      toggleItemTag={toggleItemTag}
      loading={false}
      onBackToReport={vi.fn()}
      onAnalyze={onAnalyze}
    />,
  );

  fireEvent.click(screen.getByText('Menü: mischkost'));
  fireEvent.click(screen.getByText('Gemüsepfanne'));
  fireEvent.click(screen.getByRole('button', { name: /Gemüse \/ Salat/i }));
  fireEvent.click(
    screen.getByRole('button', { name: /Report aktualisieren/i }),
  );

  expect(toggleItemFoodGroup).toHaveBeenCalledWith(0, 0, 0, 'vegetables');
  expect(toggleItemTag).not.toHaveBeenCalled();
  expect(onAnalyze).toHaveBeenCalled();
});

test('selfcheck section warns when a recognized item comes from X or Y', () => {
  render(
    <SelfCheckSection
      draftItemCount={1}
      selfCheckWeeks={[{ week_index: 0, week_label: 'Woche 1' }]}
      missingFoodGroupByWeek={new Map([[0, 0]])}
      normalizedSelfCheckWeekIndex={0}
      setSelfCheckWeekIndex={vi.fn()}
      selfCheckDays={[
        {
          day: {
            weekday: 'Dienstag',
            week_index: 0,
            week_label: 'Woche 1',
            menus: [
              {
                menu_type: 'mischkost',
                items: [
                  {
                    raw_text: 'Zucchini',
                    links: {
                      food_group: 'vegetables',
                      bls_code_letters: ['X'],
                    },
                    food_groups: ['vegetables'],
                    tags: [] as string[],
                  },
                ],
              },
            ],
          },
          dayIdx: 0,
        },
      ]}
      openMenus={{ '0-0': true }}
      setOpenMenus={vi.fn()}
      toggleItemFoodGroup={vi.fn()}
      toggleItemTag={vi.fn()}
      loading={false}
      onBackToReport={vi.fn()}
      onAnalyze={vi.fn()}
    />,
  );

  expect(
    screen.getByLabelText(/Diese Gruppe stammt aus einem X\/Y-BLS-Code/i),
  ).toBeInTheDocument();
});

test('selfcheck section does not warn for a confident single-group X or Y match', () => {
  render(
    <SelfCheckSection
      draftItemCount={1}
      selfCheckWeeks={[{ week_index: 0, week_label: 'Woche 1' }]}
      missingFoodGroupByWeek={new Map([[0, 0]])}
      normalizedSelfCheckWeekIndex={0}
      setSelfCheckWeekIndex={vi.fn()}
      selfCheckDays={[
        {
          day: {
            weekday: 'Mittwoch',
            week_index: 0,
            week_label: 'Woche 1',
            menus: [
              {
                menu_type: 'mischkost',
                items: [
                  {
                    raw_text: 'Gurkensalat',
                    links: {
                      food_group: 'vegetables',
                      confidence: 0.9684,
                      bls_code_letters: ['X'],
                    },
                    food_groups: ['vegetables'],
                    tags: [] as string[],
                  },
                ],
              },
            ],
          },
          dayIdx: 0,
        },
      ]}
      openMenus={{ '0-0': true }}
      setOpenMenus={vi.fn()}
      toggleItemFoodGroup={vi.fn()}
      toggleItemTag={vi.fn()}
      loading={false}
      onBackToReport={vi.fn()}
      onAnalyze={vi.fn()}
    />,
  );

  expect(
    screen.queryByLabelText(/Diese Gruppe stammt aus einem X\/Y-BLS-Code/i),
  ).not.toBeInTheDocument();
  expect(screen.queryByText(/Bitte prüfen/i)).not.toBeInTheDocument();
});

test('selfcheck section marks menu as recommended for review when X or Y items are open', () => {
  render(
    <SelfCheckSection
      draftItemCount={2}
      selfCheckWeeks={[{ week_index: 0, week_label: 'Woche 1' }]}
      missingFoodGroupByWeek={new Map([[0, 0]])}
      normalizedSelfCheckWeekIndex={0}
      setSelfCheckWeekIndex={vi.fn()}
      selfCheckDays={[
        {
          day: {
            weekday: 'Mittwoch',
            week_index: 0,
            week_label: 'Woche 1',
            menus: [
              {
                menu_type: 'mischkost',
                items: [
                  {
                    raw_text: 'Zucchini',
                    links: {
                      food_group: 'vegetables',
                      bls_code_letters: ['X'],
                    },
                    food_groups: ['vegetables'],
                    tags: [],
                  },
                  {
                    raw_text: 'Tomate',
                    links: {
                      food_group: 'vegetables',
                      bls_code_letters: ['X'],
                    },
                    food_groups: ['vegetables'],
                    tags: [],
                  },
                ],
              },
            ],
          },
          dayIdx: 0,
        },
      ]}
      openMenus={{ '0-0': false }}
      setOpenMenus={vi.fn()}
      toggleItemFoodGroup={vi.fn()}
      toggleItemTag={vi.fn()}
      loading={false}
      onBackToReport={vi.fn()}
      onAnalyze={vi.fn()}
    />,
  );

  expect(screen.getByText(/Zur Prüfung empfohlen/i)).toBeInTheDocument();
  expect(
    screen.getByLabelText(
      /2\/2 erkannte Gerichte stammen aus X\/Y-BLS-Codes und sind noch offen/i,
    ),
  ).toBeInTheDocument();
});

test('selfcheck section does not recommend review below the 40 percent threshold', () => {
  render(
    <SelfCheckSection
      draftItemCount={3}
      selfCheckWeeks={[{ week_index: 0, week_label: 'Woche 1' }]}
      missingFoodGroupByWeek={new Map([[0, 0]])}
      normalizedSelfCheckWeekIndex={0}
      setSelfCheckWeekIndex={vi.fn()}
      selfCheckDays={[
        {
          day: {
            weekday: 'Donnerstag',
            week_index: 0,
            week_label: 'Woche 1',
            menus: [
              {
                menu_type: 'mischkost',
                items: [
                  {
                    raw_text: 'Zucchini',
                    links: {
                      food_group: 'vegetables',
                      bls_code_letters: ['X'],
                    },
                    food_groups: ['vegetables'],
                    tags: [] as string[],
                  },
                  {
                    raw_text: 'Apfel',
                    links: {
                      food_group: 'fruit',
                      bls_code_letters: ['F'],
                    },
                    food_groups: ['fruit'],
                    tags: [] as string[],
                  },
                  {
                    raw_text: 'Reis',
                    links: {
                      food_group: 'grains_potatoes',
                      bls_code_letters: ['C'],
                    },
                    food_groups: ['grains_potatoes'],
                    tags: [] as string[],
                  },
                ],
              },
            ],
          },
          dayIdx: 0,
        },
      ]}
      openMenus={{ '0-0': false }}
      setOpenMenus={vi.fn()}
      toggleItemFoodGroup={vi.fn()}
      toggleItemTag={vi.fn()}
      loading={false}
      onBackToReport={vi.fn()}
      onAnalyze={vi.fn()}
    />,
  );

  expect(screen.queryByText(/Zur Prüfung empfohlen/i)).not.toBeInTheDocument();
});

test('selfcheck section does not recommend review for a single X or Y item', () => {
  render(
    <SelfCheckSection
      draftItemCount={1}
      selfCheckWeeks={[{ week_index: 0, week_label: 'Woche 1' }]}
      missingFoodGroupByWeek={new Map([[0, 0]])}
      normalizedSelfCheckWeekIndex={0}
      setSelfCheckWeekIndex={vi.fn()}
      selfCheckDays={[
        {
          day: {
            weekday: 'Freitag',
            week_index: 0,
            week_label: 'Woche 1',
            menus: [
              {
                menu_type: 'mischkost',
                items: [
                  {
                    raw_text: 'Zucchini',
                    links: {
                      food_group: 'vegetables',
                      bls_code_letters: ['X'],
                    },
                    food_groups: ['vegetables'],
                    tags: [] as string[],
                  },
                ],
              },
            ],
          },
          dayIdx: 0,
        },
      ]}
      openMenus={{ '0-0': false }}
      setOpenMenus={vi.fn()}
      toggleItemFoodGroup={vi.fn()}
      toggleItemTag={vi.fn()}
      loading={false}
      onBackToReport={vi.fn()}
      onAnalyze={vi.fn()}
    />,
  );

  expect(screen.queryByText(/Zur Prüfung empfohlen/i)).not.toBeInTheDocument();
});
