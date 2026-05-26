import {
  getPrimaryFoodGroup,
  toggleFoodGroup,
  toggleTag,
} from '../../app/lib/foodplan';

test('toggle helpers add and remove entries', () => {
  expect(toggleFoodGroup([], 'fish')).toEqual(['fish']);
  expect(toggleFoodGroup(['fish'], 'fish')).toEqual([]);
  expect(toggleTag([], 'wholegrain')).toEqual(['wholegrain']);
  expect(toggleTag(['wholegrain'], 'wholegrain')).toEqual([]);
});

test('getPrimaryFoodGroup prefers multi selection over link fallback', () => {
  expect(
    getPrimaryFoodGroup({
      food_groups: ['fish', 'vegetables'],
      links: { food_group: 'meat' },
    }),
  ).toBe('fish');

  expect(getPrimaryFoodGroup({ links: { food_group: 'meat' } })).toBe('meat');
});
