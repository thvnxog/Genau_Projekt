import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { StepNavigation } from '../../app/components/navigation/StepNavigation';

test('step navigation switches labels between upload and report', () => {
  const onBack = vi.fn();
  const onNext = vi.fn();

  const { rerender } = render(
    <StepNavigation
      step='upload'
      loading={false}
      onBack={onBack}
      onNext={onNext}
    />,
  );

  expect(screen.getByRole('button', { name: 'Weiter' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Zurück' })).toBeDisabled();

  rerender(
    <StepNavigation
      step='report'
      loading={false}
      onBack={onBack}
      onNext={onNext}
    />,
  );

  expect(
    screen.getByRole('button', { name: 'Weiter zum Selbstcheck' }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Zurück' }));
  fireEvent.click(
    screen.getByRole('button', { name: 'Weiter zum Selbstcheck' }),
  );

  expect(onBack).toHaveBeenCalled();
  expect(onNext).toHaveBeenCalled();
});
