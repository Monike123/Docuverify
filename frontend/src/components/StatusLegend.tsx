const ITEMS = [
  { color: "#166534", label: "System Verified — passed all checks, no critical/warning flags" },
  { color: "#854d0e", label: "Pending — soft issues; needs a human or email confirmation" },
  { color: "#991b1b", label: "Red Flagged — critical flag or failed validation" },
];

export function StatusLegend() {
  return (
    <div className="legend">
      {ITEMS.map((i) => (
        <span key={i.label} className="legend-item">
          <span className="legend-dot" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}
