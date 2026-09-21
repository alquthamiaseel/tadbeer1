import { XIcon } from './icons.jsx'

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------
// Generic centered dialog shell: a dark backdrop + a white card with a
// close button. Used by CreateProjectModal, and any other dialog the app
// grows later, so that backdrop/close/card styling only lives in one place.
// ---------------------------------------------------------------------------
export default function Modal({ isOpen, onClose, children, maxWidthClass = 'max-w-lg' }) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
      <div className={`relative w-full ${maxWidthClass} rounded-2xl bg-white p-8 shadow-2xl`}>
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-6 top-6 text-slate-400 transition hover:text-slate-600"
        >
          <XIcon className="h-5 w-5" />
        </button>
        {children}
      </div>
    </div>
  )
}
