import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Modal from './Modal.jsx'
import { useProjects } from '../context/ProjectsContext.jsx'
import { CheckCircleIcon, ChatIcon, DocumentIcon, GitBranchIcon } from './icons.jsx'

const METHODOLOGIES = ['Agile', 'Waterfall', 'Scrum', 'Kanban']

const emptyForm = {
  name: '',
  description: '',
  methodology: METHODOLOGIES[0],
  slack: '',
  asana: '',
  github: '',
}

// One label + input, light theme (this dialog sits on white, unlike the
// dark Login/Register forms that FormField was built for). `helper` is an
// optional line of grey text explaining what the field is used for.
function Field({ label, helper, children }) {
  return (
    <div>
      <label className="mb-2 block text-sm font-semibold text-slate-900">{label}</label>
      {children}
      {helper && <p className="mt-1.5 text-xs text-slate-500">{helper}</p>}
    </div>
  )
}

const inputClass =
  'w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-slate-900 placeholder-slate-400 outline-none focus:border-teal-400'

// The numbered 1-2-3 progress row at the top of the dialog: steps before
// the current one turn solid green with a checkmark, the current step is
// teal, and later steps stay a light neutral grey.
function StepIndicator({ step }) {
  return (
    <div className="mb-6 flex items-center">
      {[1, 2, 3].map((n) => (
        <div key={n} className="flex flex-1 items-center last:flex-none">
          <div
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
              n < step
                ? 'bg-green-500 text-white'
                : n === step
                  ? 'bg-teal-500 text-white'
                  : 'bg-slate-100 text-slate-400'
            }`}
          >
            {n < step ? <CheckCircleIcon className="h-4 w-4" /> : n}
          </div>
          {n < 3 && (
            <div className={`mx-2 h-0.5 flex-1 ${n < step ? 'bg-green-500' : 'bg-slate-200'}`} />
          )}
        </div>
      ))}
    </div>
  )
}

const STEP_COPY = {
  1: { title: 'Create New Project', subtitle: 'Enter the basic details for your new project' },
  2: { title: 'Create New Project', subtitle: 'Connect your project integrations' },
  3: { title: 'Create New Project', subtitle: 'Review and create your project' },
}

// One row in the step 3 review list: an icon, a label, and the value the
// user typed - or a muted placeholder-style label when they left it blank,
// since Slack/Asana/GitHub are all optional.
function ReviewRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-3 py-2 text-sm">
      <Icon className="h-4 w-4 shrink-0 text-slate-400" />
      <span className={value ? 'text-slate-900' : 'italic text-slate-400'}>
        {value || label}
      </span>
    </div>
  )
}

export default function CreateProjectModal() {
  const { isCreateModalOpen, closeCreateModal, addProject } = useProjects()
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [form, setForm] = useState(emptyForm)

  function handleChange(event) {
    const { name, value } = event.target
    setForm((previous) => ({ ...previous, [name]: value }))
  }

  function handleClose() {
    closeCreateModal()
    // Reset so the next time it opens it starts from a clean step 1.
    setStep(1)
    setForm(emptyForm)
  }

  function handleCreate() {
    const project = addProject({
      name: form.name,
      description: form.description,
      methodology: form.methodology,
      integrations: { slack: form.slack, asana: form.asana, github: form.github },
    })
    handleClose()
    navigate(`/projects/${project.id}`)
  }

  const { title, subtitle } = STEP_COPY[step]

  return (
    <Modal isOpen={isCreateModalOpen} onClose={handleClose} maxWidthClass="max-w-xl">
      <h2 className="text-2xl font-bold text-slate-900">{title}</h2>
      <p className="mt-1 mb-6 text-slate-500">{subtitle}</p>

      <StepIndicator step={step} />

      {step === 1 && (
        <div className="space-y-5">
          <Field label="Project Name">
            <input
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="e.g., E-Commerce Platform"
              className={inputClass}
              autoFocus
            />
          </Field>
          <Field label="Description">
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              placeholder="Describe your project..."
              rows={3}
              className={`${inputClass} resize-y`}
            />
          </Field>
          <Field label="Methodology">
            <select
              name="methodology"
              value={form.methodology}
              onChange={handleChange}
              className={inputClass}
            >
              {METHODOLOGIES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </Field>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <Field
            label="Slack Channel"
            helper="The AI agent will monitor this channel for requirements discussions"
          >
            <input
              name="slack"
              value={form.slack}
              onChange={handleChange}
              placeholder="#project-channel"
              className={inputClass}
              autoFocus
            />
          </Field>
          <Field
            label="Asana Project"
            helper="Tasks will be automatically created in this Asana project"
          >
            <input
              name="asana"
              value={form.asana}
              onChange={handleChange}
              placeholder="Project name or URL"
              className={inputClass}
            />
          </Field>
          <Field
            label="GitHub Repository"
            helper="Prototypes and documentation will be pushed here"
          >
            <input
              name="github"
              value={form.github}
              onChange={handleChange}
              placeholder="org/repo-name"
              className={inputClass}
            />
          </Field>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-5">
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-sm text-slate-500">Project Name</p>
            <p className="font-semibold text-slate-900">{form.name || 'Untitled Project'}</p>

            <p className="mt-3 text-sm text-slate-500">Description</p>
            <p className="text-slate-900">{form.description || 'No description provided.'}</p>

            <p className="mt-3 text-sm text-slate-500">Methodology</p>
            <p className="text-slate-900">{form.methodology}</p>

            <div className="mt-4 border-t border-slate-100 pt-3">
              <ReviewRow icon={ChatIcon} label="slack channel url" value={form.slack} />
              <ReviewRow icon={DocumentIcon} label="asana project url" value={form.asana} />
              <ReviewRow icon={GitBranchIcon} label="github repo url" value={form.github} />
            </div>
          </div>

          <p className="text-sm text-slate-500">
            Once created, the AI agent will begin monitoring your Slack channel for requirements
            and stakeholder discussions.
          </p>
        </div>
      )}

      {/* Footer navigation */}
      <div className="mt-8 flex justify-between">
        {step > 1 ? (
          <button
            onClick={() => setStep(step - 1)}
            className="rounded-lg border border-slate-200 px-5 py-2.5 font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            ← Back
          </button>
        ) : (
          <span />
        )}

        {step < 3 ? (
          <button
            onClick={() => setStep(step + 1)}
            disabled={step === 1 && !form.name.trim()}
            className="rounded-lg bg-teal-500 px-5 py-2.5 font-semibold text-white transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next →
          </button>
        ) : (
          <button
            onClick={handleCreate}
            className="flex items-center gap-2 rounded-lg bg-teal-500 px-5 py-2.5 font-semibold text-white transition hover:bg-teal-400"
          >
            <CheckCircleIcon className="h-4 w-4" />
            Create Project
          </button>
        )}
      </div>
    </Modal>
  )
}
