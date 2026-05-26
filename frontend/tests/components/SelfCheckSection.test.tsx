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
