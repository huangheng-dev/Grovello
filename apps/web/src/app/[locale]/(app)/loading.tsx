export default function Loading() {
  return <div className="page-stack" aria-busy="true"><div className="skeleton skeleton--hero" /><div className="metrics-grid">{[1, 2, 3, 4].map((item) => <div className="skeleton skeleton--card" key={item} />)}</div><div className="skeleton skeleton--panel" /></div>
}
