import { render } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router'
import App from '../App'

/** Shows the current address, so tests can check where the app navigated to. */
function Address() {
  const { pathname, search } = useLocation()
  return <output data-testid="address">{pathname + search}</output>
}

/** Render the whole app at a given address, as if the user had opened that URL. */
export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Address />
    </MemoryRouter>,
  )
}
