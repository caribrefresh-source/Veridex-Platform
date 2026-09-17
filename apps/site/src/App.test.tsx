import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { App } from './App';

afterEach(cleanup);

function renderPath(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

describe('static frontend routes', () => {
  it('renders HomePage at /', () => {
    renderPath('/');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Turn complex documents');
  });

  it('renders PlansPage at /plans', () => {
    renderPath('/plans');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Built around your organization');
  });

  it('navigates in both directions', async () => {
    const user = userEvent.setup();
    renderPath('/');
    await user.click(screen.getByRole('link', { name: 'Explore plans' }));
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Built around');
    await user.click(screen.getByRole('link', { name: /Back to home/ }));
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Turn complex documents');
  });

  it('does not render a legacy route', () => {
    renderPath('/admin/users');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Page not found');
    expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument();
  });

  it('provides a route-specific title and navigation landmarks', () => {
    renderPath('/plans');
    expect(document.title).toBe('Plans | Veridex');
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeVisible();
    expect(screen.getByRole('main')).toBeVisible();
  });
});
