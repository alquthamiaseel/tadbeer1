// ---------------------------------------------------------------------------
// Toggle
// ---------------------------------------------------------------------------
// A small on/off switch, used by the Notifications cards on Profile and
// Settings, and Settings' AI Agent Settings. Purely local UI state unless
// the caller persists `checked` itself - it doesn't assume anything about
// where the value lives.
// ---------------------------------------------------------------------------
export default function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
      className={`relative h-6 w-11 shrink-0 rounded-full transition ${
        checked ? 'bg-teal-500' : 'bg-slate-300'
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${
          checked ? 'left-5' : 'left-0.5'
        }`}
      />
    </button>
  )
}
