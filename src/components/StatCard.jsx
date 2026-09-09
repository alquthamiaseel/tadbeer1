// ---------------------------------------------------------------------------
// StatCard
// ---------------------------------------------------------------------------
// One of the 4 small summary cards at the top of the dashboard (e.g.
// "Active Projects", "Approved Items"...). It deliberately has no number -
// there is no real project data yet, so showing a fake "0" or "4" would be
// misleading. Once real data exists, a `value` prop can be added here and
// rendered between the icon and the label.
// ---------------------------------------------------------------------------
export default function StatCard({ icon: Icon, label, iconColorClass }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <div
        className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl ${iconColorClass}`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <p className="font-medium text-slate-500">{label}</p>
    </div>
  )
}
