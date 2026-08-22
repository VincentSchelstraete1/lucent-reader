export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-grid">
      {Array.from({ length: rows }).map((_, i) => (
        <div className="skeleton-card" key={i} />
      ))}
    </div>
  )
}
