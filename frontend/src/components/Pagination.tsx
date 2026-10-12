interface Props {
  page: number
  size: number
  total: number
  onPage: (page: number) => void
}

export function Pagination({ page, size, total, onPage }: Props) {
  const pages = Math.max(1, Math.ceil(total / size))
  return (
    <nav className="pagination" aria-label="Pages">
      <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} of {pages}
      </span>
      <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </nav>
  )
}
