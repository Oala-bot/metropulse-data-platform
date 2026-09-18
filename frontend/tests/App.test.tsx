import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import App from '../src/App';

test('shows the foundation status without claiming live metrics', () => {
  render(<App />);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
    'Every trip tells',
  );
  expect(screen.getByText(/Live metrics are not connected yet/)).toBeVisible();
  expect(
    screen.getByRole('link', { name: /Explore the source/ }),
  ).toHaveAttribute(
    'href',
    'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page',
  );
});
