import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import Page from '../app/page';

function previewResponse() {
  return {
    schema_version: '1.0',
    mode: 'preview',
    school_level: 'P',
    stats: { total_items: 1 },
    plan: {
      schema_version: '1.0',
      days: [
        {
          weekday: 'Montag',
          week_index: 0,
          week_label: 'Woche 1',
          menus: [
            {
              menu_type: 'mischkost',
              items: [
                {
                  raw_text: 'Gemüsepfanne',
                  portion: { value: 100, unit: 'g' },
                  food_groups: [],
                  links: { food_group: null, confidence: null },
                  tags: [],
                },
              ],
            },
          ],
        },
      ],
    },
  };
}

function analyzeResponse() {
  return {
    schema_version: '1.0',
    mode: 'dual',
    mixed: {
      summary: { score: 0.5, passed_rules: 1, applicable_rules: 2 },
      gram_hints: [],
      rules: [
        {
          id: 'rule-1',
          label: 'Eine Regel',
          applies: true,
          passed: false,
          expected: 'mind. 1',
          actual: 0,
        },
      ],
    },
    ovo_lacto_vegetarian: {
      summary: { score: 1, passed_rules: 2, applicable_rules: 2 },
      gram_hints: [],
      rules: [],
    },
  };
}

test('page drives upload, report and selfcheck flow', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.endsWith('/api/preview')) {
      return new Response(JSON.stringify(previewResponse()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.endsWith('/api/analyze')) {
      return new Response(JSON.stringify(analyzeResponse()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    throw new Error(`Unexpected fetch request: ${url}`);
  });

  vi.stubGlobal('fetch', fetchMock);

  render(<Page />);

  fireEvent.click(screen.getByRole('button', { name: /Primarstufe \(P\)/i }));

  const fileInput = document.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  const file = new File(['demo'], 'plan.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  fireEvent.change(fileInput, { target: { files: [file] } });

  fireEvent.click(screen.getByRole('button', { name: 'Weiter' }));

  await waitFor(() => {
    expect(screen.getByText('Mischkost')).toBeInTheDocument();
  });

  expect(fetchMock).toHaveBeenCalledWith('/api/preview', expect.any(Object));
  expect(fetchMock).toHaveBeenCalledWith('/api/analyze', expect.any(Object));
  expect(
    screen.getByRole('button', { name: /Jetzt überarbeiten/i }),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /Jetzt überarbeiten/i }));

  await waitFor(() => {
    expect(screen.getByText('Lebensmittelgruppen prüfen')).toBeInTheDocument();
  });
});

test('page shows upload error when school level is missing', async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);

  render(<Page />);

  const fileInput = document.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  const file = new File(['demo'], 'plan.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  fireEvent.change(fileInput, { target: { files: [file] } });

  fireEvent.click(screen.getByRole('button', { name: 'Weiter' }));

  await waitFor(() => {
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Bitte erst Primarstufe (P) oder Sekundarstufe (S) auswählen.',
    );
  });

  expect(fetchMock).not.toHaveBeenCalled();
});

test('page navigates from report to selfcheck and back', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();

    if (url.endsWith('/api/preview')) {
      return new Response(JSON.stringify(previewResponse()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.endsWith('/api/analyze')) {
      return new Response(JSON.stringify(analyzeResponse()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    throw new Error(`Unexpected fetch request: ${url}`);
  });

  vi.stubGlobal('fetch', fetchMock);

  render(<Page />);

  fireEvent.click(screen.getByRole('button', { name: /Primarstufe \(P\)/i }));
  const fileInput = document.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  fireEvent.change(fileInput, {
    target: {
      files: [
        new File(['demo'], 'plan.xlsx', {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }),
      ],
    },
  });

  fireEvent.click(screen.getByRole('button', { name: 'Weiter' }));

  await waitFor(() => {
    expect(screen.getByText('Mischkost')).toBeInTheDocument();
  });

  fireEvent.click(
    screen.getByRole('button', { name: 'Weiter zum Selbstcheck' }),
  );

  await waitFor(() => {
    expect(screen.getByText('Lebensmittelgruppen prüfen')).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole('button', { name: 'Zurück zum Report' }));

  await waitFor(() => {
    expect(screen.getByText('Ampel-Erklärung')).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole('button', { name: 'Zurück' }));

  await waitFor(() => {
    expect(screen.getByText('Datei hochladen')).toBeInTheDocument();
  });
});
