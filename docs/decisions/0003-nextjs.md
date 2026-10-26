# ADR 0003: Next.js dashboard and same-origin API boundary

Status: accepted for M01.

Use Next.js App Router, React strict mode, strict TypeScript, Tailwind CSS,
Lucide icons, TanStack Query, and Zod. Query manages refresh, retry and stale
state; Zod validates network responses. Use React Hook Form when there is a form
that benefits from it; diagnostic action buttons do not require a form library.

The browser calls same-origin Next.js routes. Only the Next.js server knows
`API_INTERNAL_URL`. Use bounded server requests and safe HTTP failure responses;
never embed Docker DNS names or database credentials in public variables.

Generate deterministic TypeScript schema literals from committed JSON schemas.
Python tests compare JSON schemas against Pydantic; TypeScript tests compare
generated literals against JSON and exercise runtime validation. Future product
sections must explicitly state that they are scheduled for later milestones.
