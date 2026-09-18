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
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('AI decisions your organization can defend');
  });

  it('renders PlansPage at /plans', () => {
    renderPath('/plans');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Choose control first');
  });

  it('navigates in both directions', async () => {
    const user = userEvent.setup();
    renderPath('/');
    await user.click(screen.getByRole('link', { name: 'Explore deployment options' }));
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Choose control first');
    await user.click(screen.getByRole('link', { name: /Return home/ }));
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('AI decisions your organization can defend');
  });

  it('does not render a legacy route', () => {
    renderPath('/admin/users');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Page not found');
    expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument();
  });

  it('provides titles and navigation landmarks', () => {
    renderPath('/plans');
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeVisible();
    expect(screen.getByRole('main')).toBeVisible();
  });
});

