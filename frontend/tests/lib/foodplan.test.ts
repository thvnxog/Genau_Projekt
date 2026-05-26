import {
  getPrimaryFoodGroup,
  toggleFoodGroup,
  toggleTag,
} from '../../app/lib/foodplan';

test('toggle helpers add and remove entries', () => {
  // Prüft die kleinen Hilfsfunktionen für das Ein- und Ausschalten von Chips.
  expect(toggleFoodGroup([], 'fish')).toEqual(['fish']);
  expect(toggleFoodGroup(['fish'], 'fish')).toEqual([]);
  expect(toggleTag([], 'wholegrain')).toEqual(['wholegrain']);
  expect(toggleTag(['wholegrain'], 'wholegrain')).toEqual([]);
});

test('getPrimaryFoodGroup prefers multi selection over link fallback', () => {
  // Wenn mehrere Gruppen gesetzt sind, soll die erste als Hauptgruppe gelten.
  expect(
    getPrimaryFoodGroup({
      food_groups: ['fish', 'vegetables'],
      links: { food_group: 'meat' },
    }),
  ).toBe('fish');

  expect(getPrimaryFoodGroup({ links: { food_group: 'meat' } })).toBe('meat');
});
