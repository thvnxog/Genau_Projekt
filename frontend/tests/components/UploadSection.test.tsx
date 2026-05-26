import { createRef } from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { UploadSection } from '../../app/components/upload/UploadSection';

function renderUploadSection(file: File | null = null) {
  const fileInputRef = createRef<HTMLInputElement>();
  fileInputRef.current = {
    click: vi.fn(),
  } as unknown as HTMLInputElement;

  const setFile = vi.fn();
  const setIsDragging = vi.fn();
  const setSchoolLevel = vi.fn();
  const clearSelectedFile = vi.fn();

  render(
    <UploadSection
      file={file}
      isDragging={false}
      fileInputRef={fileInputRef}
      setFile={setFile}
      setIsDragging={setIsDragging}
      schoolLevel={null}
      setSchoolLevel={setSchoolLevel}
      clearSelectedFile={clearSelectedFile}
    />,
  );

  return {
    fileInputRef,
    setFile,
    setIsDragging,
    setSchoolLevel,
    clearSelectedFile,
  };
}

test('upload section opens help modal and exposes template links', () => {
  renderUploadSection();

  fireEvent.click(screen.getByRole('button', { name: /hilfe/i }));

  expect(screen.getByRole('dialog')).toHaveTextContent(
    'So startest du in 30 Sekunden',
  );
  expect(screen.getByRole('link', { name: /1-Wochen-Plan/i })).toHaveAttribute(
    'href',
    '/1_Wochen_Plan.xlsx',
  );
  expect(
    screen.getByRole('button', { name: /Primarstufe \(P\)/i }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: /Sekundarstufe \(S\)/i }),
  ).toBeInTheDocument();
});

test('upload section allows school selection and file removal', () => {
  const file = new File(['demo'], 'plan.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const { setSchoolLevel, clearSelectedFile } = renderUploadSection(file);

  fireEvent.click(screen.getByRole('button', { name: /Primarstufe \(P\)/i }));
  fireEvent.click(screen.getByRole('button', { name: /Sekundarstufe \(S\)/i }));
  fireEvent.click(screen.getByRole('button', { name: /Datei entfernen/i }));

  expect(setSchoolLevel).toHaveBeenCalledWith('P');
  expect(setSchoolLevel).toHaveBeenCalledWith('S');
  expect(clearSelectedFile).toHaveBeenCalled();
  expect(screen.getByText('plan.xlsx')).toBeInTheDocument();
});
