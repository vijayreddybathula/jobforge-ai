const MAP = {
  ASSISTED_APPLY:       { label: 'Apply',    cls: 'badge-apply' },
  ELIGIBLE_AUTO_SUBMIT: { label: 'Auto',     cls: 'badge-auto' },
  VALIDATE:             { label: 'Validate', cls: 'badge-validate' },
  SKIP:                 { label: 'Skip',     cls: 'badge-skip' },
  NOT_SCORED:           { label: 'Unscored', cls: 'badge-default' },
  REJECTED:             { label: 'Rejected', cls: 'badge-skip' },
}

export default function VerdictBadge({ verdict }) {
  const v = MAP[verdict] || MAP.NOT_SCORED
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${v.cls}`}>
      {v.label}
    </span>
  )
}
