"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CapabilitiesSchema,
  DiagnosticJobSchema,
  ReadyHealthSchema,
  type DiagnosticRequest,
  type ReadyHealth,
} from "@earthmind/contracts";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Box,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Command,
  Cpu,
  Database,
  FlaskConical,
  Globe2,
  Layers3,
  LayoutDashboard,
  LoaderCircle,
  Map as MapIcon,
  Menu,
  Orbit,
  Play,
  RefreshCw,
  Route,
  Server,
  Settings,
  ShieldCheck,
  Terminal,
  TriangleAlert,
  Workflow,
  X,
  Zap,
  ChartNoAxesCombined,
  type LucideIcon,
} from "lucide-react";
import { requestJSON } from "@/lib/client";

const navigation: { label: string; icon: LucideIcon; active: boolean }[] = [
  { label: "Overview", icon: LayoutDashboard, active: true },
  { label: "City Explorer", icon: MapIcon, active: false },
  { label: "Scenario Studio", icon: Layers3, active: false },
  { label: "Simulation Laboratory", icon: FlaskConical, active: false },
  { label: "Traffic Intelligence", icon: Route, active: false },
  { label: "AI Command Center", icon: BrainCircuit, active: false },
  { label: "Analytics", icon: ChartNoAxesCombined, active: false },
  { label: "System Status", icon: Activity, active: true },
  { label: "Settings", icon: Settings, active: false },
];

type HealthSnapshot = {
  health: ReadyHealth;
  apiReachable: boolean;
  checkedAt: number;
  lastSuccessfulAt: number | null;
};
const futureDescriptions: Record<string, string> = {
  "City Explorer":
    "Explore connected urban networks and their spatial context.",
  "Scenario Studio": "Define and compare urban intervention scenarios.",
  "Simulation Laboratory":
    "Run controlled traffic experiments against a validated network.",
  "Traffic Intelligence": "Inspect traffic patterns and network performance.",
  "AI Command Center": "Work with grounded urban intelligence and forecasting.",
  Analytics: "Compare evidence across completed experiments.",
  Settings: "Manage workspace configuration and platform preferences.",
};

function formatTime(timestamp: number | null | undefined) {
  return timestamp
    ? new Date(timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "Not checked yet";
}

function StatusBadge({
  status,
  label,
}: {
  status: "ok" | "error" | "pending";
  label?: string;
}) {
  return (
    <span className={`status-badge ${status}`}>
      <span className="status-dot" />
      {label ??
        (status === "ok"
          ? "Healthy"
          : status === "error"
            ? "Unavailable"
            : "Checking")}
    </span>
  );
}

function DiagnosticPanel({ connected }: { connected: boolean }) {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (request: DiagnosticRequest) =>
      requestJSON("/api/diagnostics", DiagnosticJobSchema, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }),
  });
  const jobQuery = useQuery({
    queryKey: ["diagnostic", mutation.data?.job_id],
    enabled: Boolean(mutation.data?.job_id),
    initialData: mutation.data,
    queryFn: () =>
      requestJSON(
        `/api/diagnostics/${mutation.data!.job_id}`,
        DiagnosticJobSchema,
      ),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 1_000
        : false,
    staleTime: 0,
  });
  const job = jobQuery.data ?? mutation.data;
  const busy =
    mutation.isPending ||
    (job !== undefined && ["queued", "running"].includes(job.status));
  useEffect(() => {
    if (job?.status === "succeeded") {
      void client.invalidateQueries({ queryKey: ["capabilities"] });
      void client.invalidateQueries({ queryKey: ["health"] });
    }
  }, [job?.status, client]);
  return (
    <section
      className="panel diagnostics-panel"
      aria-labelledby="diagnostics-title"
    >
      <div className="panel-heading">
        <div>
          <p className="section-kicker">VERIFY THE FOUNDATION</p>
          <h2 id="diagnostics-title">Runtime diagnostics</h2>
        </div>
        <Terminal size={19} className="muted-icon" />
      </div>
      <p className="panel-description">
        Submit a real job to the simulation worker. SUMO verification executes
        a tiny, labeled synthetic fixture to check the installed runtime.
      </p>
      <div className="diagnostic-actions">
        <button
          className="action-button"
          disabled={!connected || busy}
          onClick={() => mutation.mutate({ kind: "diagnostic" })}
        >
          {busy && job?.kind === "diagnostic" ? (
            <LoaderCircle className="spin" size={15} />
          ) : (
            <Workflow size={15} />
          )}
          Run worker diagnostic
        </button>
        <button
          className="action-button secondary"
          disabled={!connected || busy}
          onClick={() => mutation.mutate({ kind: "sumo_runtime" })}
        >
          {busy && job?.kind === "sumo_runtime" ? (
            <LoaderCircle className="spin" size={15} />
          ) : (
            <Play size={15} />
          )}
          Verify SUMO runtime
        </button>
      </div>
      {(mutation.isError || jobQuery.isError) && (
        <div className="inline-error" role="alert">
          <TriangleAlert size={16} />
          <span>
            {mutation.error?.message ??
              jobQuery.error?.message ??
              "Diagnostic request failed"}
          </span>
        </div>
      )}
      {job ? (
        <div className="job-result" aria-live="polite">
          <div className="job-heading">
            <span>
              <span className={`job-dot ${job.status}`} />
              {job.kind === "sumo_runtime"
                ? "SUMO runtime verification"
                : "Worker diagnostic"}
            </span>
            <span className="job-status">{job.status}</span>
          </div>
          <p className="job-id">Job {job.job_id}</p>
          {busy && (
            <p className="job-waiting">
              <LoaderCircle className="spin" size={13} />
              Waiting for the worker to finish…
            </p>
          )}
          {job.error && <p className="inline-error">{job.error}</p>}
          {job.result && (
            <pre aria-label="Diagnostic result">
              {JSON.stringify(job.result, null, 2)}
            </pre>
          )}
        </div>
      ) : (
        <div className="diagnostic-empty">
          <Box size={21} />
          <span>No diagnostic jobs submitted in this session.</span>
          <span className="quiet-label">READY WHEN YOU ARE</span>
        </div>
      )}
    </section>
  );
}

export function Dashboard() {
  const [section, setSection] = useState("Overview");
  const [menuOpen, setMenuOpen] = useState(false);
  const client = useQueryClient();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async (): Promise<HealthSnapshot> => {
      const response = await fetch("/api/health", {
        cache: "no-store",
        signal: AbortSignal.timeout(8_000),
      });
      if (![200, 503].includes(response.status))
        throw new Error("Platform health is unavailable");
      const result = ReadyHealthSchema.parse(await response.json());
      const now = Date.now();
      const previous = client.getQueryData<HealthSnapshot>(["health"]);
      const apiReachable =
        response.headers.get("X-Earthmind-Api-Reachable") === "true";
      return {
        health: result,
        apiReachable,
        checkedAt: now,
        lastSuccessfulAt:
          result.status === "ok" && apiReachable
            ? now
            : (previous?.lastSuccessfulAt ?? null),
      };
    },
    refetchInterval: 15_000,
  });
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => requestJSON("/api/capabilities", CapabilitiesSchema),
    refetchInterval: 15_000,
  });
  const checking = health.isPending;
  const offline = health.isError || health.data?.apiReachable === false;
  const healthy = !offline && health.data?.health.status === "ok";
  const caps = capabilities.data;
  const checks = health.data?.health.checks;
  const refresh = () => {
    void health.refetch();
    void capabilities.refetch();
  };
  const status: "ok" | "error" | "pending" = checking
    ? "pending"
    : healthy
      ? "ok"
      : "error";
  const showOverview = section === "Overview" || section === "System Status";
  const serviceCards: {
    label: string;
    detail: string;
    icon: LucideIcon;
    state: "ok" | "error" | "pending";
  }[] = [
    {
      label: "API service",
      detail: "FastAPI · versioned API",
      icon: Server,
      state: checking ? "pending" : offline ? "error" : "ok",
    },
    {
      label: "Spatial database",
      detail: "PostgreSQL + PostGIS",
      icon: Database,
      state: offline ? "error" : (checks?.database ?? "pending"),
    },
    {
      label: "Message broker",
      detail: "Redis · job transport",
      icon: Zap,
      state: offline ? "error" : (checks?.redis ?? "pending"),
    },
    {
      label: "Simulation worker",
      detail: "Heartbeat + diagnostic jobs",
      icon: Workflow,
      state: offline ? "error" : (checks?.worker ?? "pending"),
    },
  ];
  return (
    <div className="mission-shell">
      {menuOpen && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside
        className={`sidebar ${menuOpen ? "is-open" : ""}`}
        aria-label="Workspace navigation"
      >
        <a
          className="wordmark"
          href="#overview"
          onClick={() => setSection("Overview")}
        >
          <span className="brand-mark">
            <Orbit size={23} />
          </span>
          <span>
            EARTHMIND<small>URBAN INTELLIGENCE</small>
          </span>
        </a>
        <p className="nav-label">
          WORKSPACE <span>M01</span>
        </p>
        <nav aria-label="Main navigation">
          {navigation.map(({ label, icon: Icon, active }) => (
            <button
              key={label}
              title={label}
              aria-label={label}
              aria-current={section === label ? "page" : undefined}
              className={section === label ? "nav-item selected" : "nav-item"}
              onClick={() => {
                setSection(label);
                setMenuOpen(false);
              }}
            >
              <Icon size={17} />
              <span>{label}</span>
              {!active && <span className="nav-soon">LATER</span>}
              {section === label && <span className="nav-active-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="workspace-avatar">
            <Globe2 size={18} />
          </div>
          <div>
            <strong>Local workspace</strong>
            <span>Foundation environment</span>
          </div>
          <ChevronRight size={14} />
        </div>
      </aside>
      <main id="overview">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="menu-toggle"
              aria-label={menuOpen ? "Close navigation" : "Open navigation"}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <X size={19} /> : <Menu size={19} />}
            </button>
            <span>Workspace</span>
            <ChevronRight size={12} />
            <strong>{section}</strong>
          </div>
          <div className="topbar-right">
            <span className="environment-tag">
              <span />
              LOCAL DEVELOPMENT
            </span>
            <span className="keyboard-hint">
              <Command size={11} /> M01
            </span>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">
                <span />
                MISSION CONTROL
              </p>
              <h1>{section === "Overview" ? "Platform overview" : section}</h1>
              <p className="subtitle">AI-Powered Urban Intelligence Platform</p>
            </div>
            <button
              className="refresh-button"
              onClick={refresh}
              disabled={health.isFetching || capabilities.isFetching}
            >
              <RefreshCw
                size={14}
                className={health.isFetching ? "spin" : ""}
              />
              Refresh status
            </button>
          </div>
          {showOverview ? (
            <>
              <section className="hero" aria-label="Platform foundation">
                <div className="hero-content">
                  <span className="hero-badge">
                    <ShieldCheck size={13} />
                    M01 · PLATFORM FOUNDATION
                  </span>
                  <h2>
                    Intelligence starts
                    <br />
                    with a solid foundation.
                  </h2>
                  <p>
                    Connected infrastructure. Observable services.
                    <br className="desktop-break" /> A verified runtime for what
                    comes next.
                  </p>
                  <a href="#system-health" className="hero-link">
                    Explore system health <ArrowUpRight size={15} />
                  </a>
                </div>
                <div className="orbital" aria-hidden="true">
                  <div className="orbital-ring ring-one" />
                  <div className="orbital-ring ring-two" />
                  <div className="orbital-ring ring-three" />
                  <div className="orbital-globe">
                    <Globe2 strokeWidth={0.6} />
                    <div className="orbital-point point-one" />
                    <div className="orbital-point point-two" />
                  </div>
                  <span className="orbital-label">
                    <span />
                    FOUNDATION LAYER CONNECTED
                  </span>
                </div>
                <span className="hero-coordinate" aria-hidden="true">
                  EARTHMIND / SYSTEM 01
                </span>
              </section>
              <section
                id="system-health"
                className="services-section"
                aria-labelledby="system-health-title"
              >
                <div className="section-heading">
                  <div>
                    <span className="section-index">01</span>
                    <h2 id="system-health-title">System health</h2>
                  </div>
                  <StatusBadge
                    status={status}
                    label={
                      checking
                        ? "Connecting to platform"
                        : healthy
                          ? "All systems operational"
                          : offline
                            ? "Platform unavailable"
                            : "Services need attention"
                    }
                  />
                </div>
                {offline && (
                  <div className="error-banner" role="alert">
                    <TriangleAlert size={18} />
                    <div>
                      <strong>Platform unavailable</strong>
                      <p>
                        Health checks could not reach the platform. Check the
                        services and retry.
                      </p>
                    </div>
                    <button onClick={refresh}>
                      Retry connection <ArrowRight size={14} />
                    </button>
                  </div>
                )}
                {!offline && health.data?.health.status === "degraded" && (
                  <div className="error-banner degraded" role="alert">
                    <TriangleAlert size={17} />
                    <div>
                      <strong>Some services need attention</strong>
                      <p>
                        Readiness checks are reporting a dependency failure.
                        Review the service cards below.
                      </p>
                    </div>
                    <button onClick={refresh}>
                      Retry checks <RefreshCw size={14} />
                    </button>
                  </div>
                )}
                <div className="service-grid" aria-busy={checking}>
                  {serviceCards.map(({ label, detail, icon: Icon, state }) => (
                    <article
                      key={label}
                      className={`service-card ${checking ? "loading-card" : ""}`}
                    >
                      <div className="card-top">
                        <span className="service-icon">
                          <Icon size={18} />
                        </span>
                        <StatusBadge status={state} />
                      </div>
                      <h3>{label}</h3>
                      <p>{detail}</p>
                      <div className="service-card-footer">
                        <span>
                          {state === "pending" ? (
                            <span className="skeleton-line animate-pulse" />
                          ) : state === "ok" ? (
                            "Connection verified"
                          ) : (
                            "Check required"
                          )}
                        </span>
                        {state === "ok" ? (
                          <Check size={13} />
                        ) : (
                          <ArrowUpRight size={13} />
                        )}
                      </div>
                    </article>
                  ))}
                </div>
                <div className="check-meta">
                  <span>
                    <Clock3 size={12} />
                    Last successful check{" "}
                    <strong>{formatTime(health.data?.lastSuccessfulAt)}</strong>
                  </span>
                  <span>
                    <span className="live-dot" />
                    Auto-refresh every 15 seconds
                  </span>
                </div>
              </section>
              <div className="detail-grid">
                <DiagnosticPanel connected={healthy} />
                <section
                  className="panel capability-panel"
                  aria-labelledby="capabilities-title"
                >
                  <div className="panel-heading">
                    <div>
                      <p className="section-kicker">PLATFORM INVENTORY</p>
                      <h2 id="capabilities-title">Runtime & capabilities</h2>
                    </div>
                    <Cpu size={19} className="muted-icon" />
                  </div>
                  <div className="runtime-line">
                    <span className="runtime-icon">
                      <FlaskConical size={20} />
                    </span>
                    <div>
                      <strong>SUMO simulation runtime</strong>
                      <span>Native worker runtime verification</span>
                    </div>
                    <StatusBadge
                      status={
                        capabilities.isPending
                          ? "pending"
                          : caps?.capabilities.simulation_runtime
                            ? "ok"
                            : "error"
                      }
                      label={
                        capabilities.isPending
                          ? "Checking"
                          : caps?.capabilities.simulation_runtime
                            ? "Verified"
                            : "Not verified"
                      }
                    />
                  </div>
                  {caps?.runtime && (
                    <dl className="runtime-details">
                      <div>
                        <dt>Architecture</dt>
                        <dd>{caps.runtime.architecture}</dd>
                      </div>
                      <div>
                        <dt>Verified at</dt>
                        <dd>
                          {new Date(
                            caps.runtime.checked_at,
                          ).toLocaleTimeString()}
                        </dd>
                      </div>
                      <div className="runtime-version">
                        <dt>Runtime version</dt>
                        <dd>{caps.runtime.version}</dd>
                      </div>
                    </dl>
                  )}
                  {capabilities.isError && (
                    <p className="inline-error" role="alert">
                      Capability inventory is unavailable. Retry the platform
                      checks.
                    </p>
                  )}
                  <div className="capability-list">
                    <div>
                      <span>
                        <CheckCircle2 size={13} />
                        Versioned API & diagnostics
                      </span>
                      <span
                        className={
                          caps?.capabilities.api ? "enabled-tag" : "pending-tag"
                        }
                      >
                        {caps ? "ENABLED" : "CHECKING"}
                      </span>
                    </div>
                    <div>
                      <span>
                        <Route size={13} />
                        Dubai network import
                      </span>
                      <span className="later-tag">LATER MILESTONE</span>
                    </div>
                    <div>
                      <span>
                        <Activity size={13} />
                        Traffic simulation
                      </span>
                      <span className="later-tag">LATER MILESTONE</span>
                    </div>
                    <div>
                      <span>
                        <BrainCircuit size={13} />
                        AI forecasting
                      </span>
                      <span className="later-tag">LATER MILESTONE</span>
                    </div>
                  </div>
                  <p className="capability-note">
                    Capability status reflects the current backend. Future
                    workflows are not enabled in M01.
                  </p>
                </section>
              </div>
              <section className="foundation-note">
                <span className="note-icon">
                  <Layers3 size={20} />
                </span>
                <div>
                  <h2>A connected foundation. A deliberate next step.</h2>
                  <p>
                    This milestone establishes infrastructure, health checks and
                    runtime diagnostics. City models, traffic scenarios and AI
                    forecasts are reserved for later milestones.
                  </p>
                </div>
                <span className="foundation-tag">FOUNDATION ONLY</span>
              </section>
            </>
          ) : (
            <section className="future-panel">
              <span className="future-icon">
                <Box size={28} />
              </span>
              <p className="eyebrow">LATER MILESTONE</p>
              <h2>{section}</h2>
              <p>{futureDescriptions[section]}</p>
              <div className="scope-notice">
                <ShieldCheck size={17} />
                <span>
                  This workspace is scoped to the M01 foundation. This workflow
                  is not enabled yet.
                </span>
              </div>
              <button
                className="action-button"
                onClick={() => setSection("Overview")}
              >
                Return to overview <ArrowRight size={15} />
              </button>
            </section>
          )}
          <footer>
            <span>
              <Orbit size={13} />
              EARTHMIND <span className="footer-divider" />
              Foundation, connected.
            </span>
            <div>
              <span>VERSION {caps?.version ?? "—"}</span>
              <span className="footer-divider" />
              <span>MILESTONE {caps?.milestone ?? "M01"}</span>
              <a href="/api/health">
                Readiness API <ArrowUpRight size={11} />
              </a>
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
