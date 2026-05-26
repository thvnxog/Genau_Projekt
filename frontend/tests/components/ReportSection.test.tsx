import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { ReportSection } from '../../app/components/report/ReportSection';

const baseReport = {
  summary: { score: 0.5, passed_rules: 1, applicable_rules: 2 },
  gram_hints: [],
  rules: [
    {
      id: 'rule-1',
      label: 'Fisch ist vorhanden',
      applies: true,
      passed: true,
      expected: 'mind. 1',
      actual: 1,
    },
    {
      id: 'rule-2',
      label: 'Gemüse ist vorhanden',
      applies: true,
      passed: false,
      expected: 'mind. 2',
      actual: 1,
      notes: 'Noch ein Gemüsegericht ergänzen.',
    },
  ],
};

function renderDualReport() {
  // Baut einen Report mit zwei Ernährungsformen auf, damit die Anzeige getestet werden kann.
  const onGoToSelfcheck = vi.fn();

  render(
    <ReportSection
      reportData={{
        mode: 'dual',
        mixed: baseReport,
        ovo_lacto_vegetarian: baseReport,
      }}
      loading={false}
      missingFoodGroupCount={2}
      activeWeekIndex={0}
      setActiveWeekIndex={vi.fn()}
      onGoToSelfcheck={onGoToSelfcheck}
    />,
  );

  return { onGoToSelfcheck };
}

test('report section shows summary cards and selfcheck hint', () => {
  // Der Report soll Score-Karten und den Hinweis zum Selbstcheck anzeigen.
  const { onGoToSelfcheck } = renderDualReport();

  expect(screen.getByText('Ampel-Erklärung')).toBeInTheDocument();
  expect(screen.getByText('Mischkost')).toBeInTheDocument();
  expect(screen.getByText('Vegetarisch')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Jetzt überarbeiten/i }));
  expect(onGoToSelfcheck).toHaveBeenCalled();
});

test('report section supports monthly week switching', () => {
  // Bei Monatsplänen kann der Nutzer zwischen den Wochen umschalten.
  const setActiveWeekIndex = vi.fn();

  render(
    <ReportSection
      reportData={{
        mode: 'monthly_dual',
        monthly_summary: {
          weeks: 2,
          mixed: baseReport.summary,
          ovo_lacto_vegetarian: baseReport.summary,
        },
        weekly_reports: [
          {
            week_index: 0,
            week_label: 'Woche 1',
            mixed: baseReport,
            ovo_lacto_vegetarian: baseReport,
          },
          {
            week_index: 1,
            week_label: 'Woche 2',
            mixed: baseReport,
            ovo_lacto_vegetarian: baseReport,
          },
        ],
      }}
      loading={false}
      missingFoodGroupCount={0}
      activeWeekIndex={0}
      setActiveWeekIndex={setActiveWeekIndex}
      onGoToSelfcheck={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'Woche 2' }));

  expect(setActiveWeekIndex).toHaveBeenCalledWith(1);
});
