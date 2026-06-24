import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { getCities, getDoctors } from "../api/client";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  themeVariables: {
    darkMode: true,
    background: "#070c1a",
    primaryColor: "#1e3a5f",
    primaryTextColor: "#e2e8f0",
    primaryBorderColor: "#334155",
    lineColor: "#6366f1",
    secondaryColor: "#1e293b",
    tertiaryColor: "#0f172a",
    edgeLabelBackground: "#1e293b",
    clusterBkg: "#1e293b",
    clusterBorder: "#334155",
    titleColor: "#e2e8f0",
    nodeTextColor: "#e2e8f0",
    fontFamily: "Barlow, sans-serif",
  },
});

const ARCH_DIAGRAM = `
flowchart TB
    subgraph Client["React + Vite  (Vercel)"]
        direction TB
        P(["Patient"])
        D(["Doctor"])
        A(["Admin"])
        UI["Chat / Appointments / Voice Input\\nQueue / Schedule / History\\nDashboard / Doctor CRUD"]
        P & D & A --> UI
    end

    subgraph Server["FastAPI  (Render)"]
        direction TB
        REST["REST API\\n/auth  /chat  /doctor  /admin  /cities"]
        AGT["Agent Orchestrator\\nTool-call loop  (max 6 iterations)"]
        REST --> AGT
    end

    subgraph MCP["MCP Server  (/mcp)"]
        direction LR
        T1["list_cities  /  list_clinics_in_city\\nlist_doctors_in_clinic  /  list_doctors"]
        T2["check_availability\\nbook_appointment  /  cancel_appointment"]
        T3["list_patient_appts\\nget_report_stats"]
    end

    LLM["OpenAI  (gpt-4.1-mini)\\nTool calls / Symptom triage / Fuzzy matching"]

    subgraph DB["PostgreSQL  (Neon)"]
        direction LR
        GEO["10 Cities  20 Clinics  60 Doctors\\nDoctorAvailability  /  80+ User accounts"]
        DATA["Appointments  /  ChatThreads\\nChatMessages  /  AuthTokens"]
    end

    UI -- "Bearer token / JSON" --> REST
    AGT -- "tool_calls" --> MCP
    AGT <-- "chat completions" --> LLM
    MCP -- "SQLAlchemy ORM" --> DB
    REST -- "SQLAlchemy ORM" --> DB
`;

function MermaidChart({ chart }) {
  const ref = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const id = "arch-" + Math.random().toString(36).slice(2);
    mermaid.render(id, chart)
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => { cancelled = true; };
  }, [chart]);

  if (error) return <pre style={{ color: "#fca5a5", fontSize: 12 }}>{error}</pre>;
  return <div ref={ref} className="mermaidWrap" />;
}

const TECH = ["React 18", "FastAPI", "MCP", "OpenAI", "PostgreSQL", "Neon", "Render", "Vercel", "SQLAlchemy 2.0", "Web Speech API"];

const ROLES = [
  {
    title: "Patient",
    color: "rolePatient",
    features: [
      "Chat-based appointment booking",
      "City → Clinic → Doctor guided flow",
      "Voice input (Web Speech API, en-IN)",
      "Symptom triage to specialization",
      "View and cancel appointments",
      "Persistent chat threads across sessions",
    ],
  },
  {
    title: "Doctor",
    color: "roleDoctor",
    features: [
      "Today's queue with Done / No-Show actions",
      "Clinical notes on individual appointments",
      "Weekly schedule editor (day-level windows)",
      "Full appointment history with filters",
      "LLM report assistant with auto-notification",
      "Auto-provisioned login on system startup",
    ],
  },
  {
    title: "Admin",
    color: "roleAdmin",
    features: [
      "Clinic dashboard with live stats",
      "Add / edit / deactivate doctors",
      "New doctor auto-gets schedule + login",
      "Filterable appointment log",
      "Scoped to their clinic only",
      "Auto-provisioned per-clinic credentials",
    ],
  },
];

const FLOW_STEPS = [
  { label: "Pick City", sub: "10 Indian cities" },
  { label: "Pick Clinic", sub: "2 per city" },
  { label: "Pick Doctor", sub: "Fuzzy name matching" },
  { label: "Check Slots", sub: "Data-driven availability" },
  { label: "Confirmed", sub: "Notification sent" },
];

const MCP_TOOLS = [
  { name: "list_cities", tag: "geo" },
  { name: "list_clinics_in_city", tag: "geo" },
  { name: "list_doctors_in_clinic", tag: "geo" },
  { name: "list_doctors", tag: "geo" },
  { name: "check_doctor_availability", tag: "booking" },
  { name: "book_appointment", tag: "booking" },
  { name: "cancel_appointment", tag: "booking" },
  { name: "list_patient_appointments", tag: "patient" },
  { name: "get_doctor_report_stats", tag: "doctor" },
  { name: "send_doctor_notification", tag: "notify" },
];

const TAG_COLORS = {
  geo: "tagGeo",
  booking: "tagBooking",
  patient: "tagPatient",
  doctor: "tagDoctor",
  notify: "tagNotify",
};

export default function Overview({ onBack }) {
  const [stats, setStats] = useState({ cities: 0, clinics: 0, doctors: 0 });

  useEffect(() => {
    getCities()
      .then((cities) => {
        setStats((s) => ({ ...s, cities: cities.length }));
        return Promise.all(
          cities.map((c) =>
            fetch(`${import.meta.env.VITE_API_BASE_URL || ""}/api/clinics?city=${encodeURIComponent(c.name)}`)
              .then((r) => r.json()).catch(() => [])
          )
        );
      })
      .then((clinicArrays) => {
        const total = clinicArrays.reduce((s, arr) => s + (arr?.length || 0), 0);
        setStats((s) => ({ ...s, clinics: total }));
      })
      .catch(() => {});

    getDoctors()
      .then((docs) => setStats((s) => ({ ...s, doctors: docs.length })))
      .catch(() => {});
  }, []);

  return (
    <div className="overviewShell">
      {/* Nav */}
      <div className="overviewNav">
        <button className="overviewBackBtn" onClick={onBack}>← Back</button>
        <span className="pill">Live Overview</span>
      </div>

      {/* Hero */}
      <section className="overviewHero">
        <div className="overviewHeroBadges">
          <span className="pill">MCP</span>
          <span className="pill">Pan-India</span>
          <span className="pill">3 Roles</span>
          <span className="pill">Production</span>
        </div>
        <h1 className="overviewTitle">Agentic Appointment Assistant</h1>
        <p className="overviewSubtitle">
          A production-ready, multi-tenant healthcare scheduler where an LLM orchestrates
          real-time booking, triage, doctor queues, and clinic management via the
          Model Context Protocol.
        </p>
        <div className="overviewTechRow">
          {TECH.map((t) => (
            <span key={t} className="techPill">{t}</span>
          ))}
        </div>
        <div className="overviewLinks">
          <a href="https://agentic-appointment-assistant-mcp.vercel.app/" target="_blank" rel="noopener noreferrer" className="overviewLinkBtn primary">
            Live Demo
          </a>
          <a href="https://github.com/Peeyush237/Agentic-Appointment-Assistant-MCP" target="_blank" rel="noopener noreferrer" className="overviewLinkBtn">
            GitHub
          </a>
        </div>
      </section>

      {/* Live Stats */}
      <section className="overviewSection">
        <h2 className="overviewSectionTitle">Live Scale</h2>
        <div className="overviewStats">
          <div className="overviewStatCard">
            <div className="overviewStatNum">{stats.cities || 10}</div>
            <div className="overviewStatLabel">Cities</div>
          </div>
          <div className="overviewStatCard">
            <div className="overviewStatNum">{stats.clinics || 20}</div>
            <div className="overviewStatLabel">Clinics</div>
          </div>
          <div className="overviewStatCard">
            <div className="overviewStatNum">{stats.doctors || 60}</div>
            <div className="overviewStatLabel">Doctors</div>
          </div>
          <div className="overviewStatCard">
            <div className="overviewStatNum">3</div>
            <div className="overviewStatLabel">User Roles</div>
          </div>
          <div className="overviewStatCard">
            <div className="overviewStatNum">10+</div>
            <div className="overviewStatLabel">MCP Tools</div>
          </div>
          <div className="overviewStatCard">
            <div className="overviewStatNum">80+</div>
            <div className="overviewStatLabel">Auto Accounts</div>
          </div>
        </div>
      </section>

      {/* Architecture Diagram */}
      <section className="overviewSection">
        <h2 className="overviewSectionTitle">System Architecture</h2>
        <p className="overviewSectionSub">
          End-to-end data flow — from the browser to the LLM to the database.
        </p>
        <div className="overviewDiagramCard surfaceCard">
          <MermaidChart chart={ARCH_DIAGRAM} />
        </div>
      </section>

      {/* Role Cards */}
      <section className="overviewSection">
        <h2 className="overviewSectionTitle">Three Distinct Roles</h2>
        <p className="overviewSectionSub">
          Each role has its own auth flow, UI, and auto-provisioned credentials.
        </p>
        <div className="overviewRoleGrid">
          {ROLES.map((r) => (
            <div key={r.title} className={`overviewRoleCard surfaceCard ${r.color}`}>
              <h3 className="overviewRoleTitle">{r.title}</h3>
              <ul className="overviewRoleList">
                {r.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Booking Flow */}
      <section className="overviewSection">
        <h2 className="overviewSectionTitle">LLM-Guided Booking Flow</h2>
        <p className="overviewSectionSub">
          The LLM uses MCP tools to guide patients step-by-step — no form-filling needed.
        </p>
        <div className="overviewFlowRow">
          {FLOW_STEPS.map((step, i) => (
            <React.Fragment key={step.label}>
              <div className="overviewFlowStep surfaceCard">
                <div className="overviewFlowLabel">{step.label}</div>
                <div className="overviewFlowSub">{step.sub}</div>
              </div>
              {i < FLOW_STEPS.length - 1 && (
                <div className="overviewFlowArrow">→</div>
              )}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* MCP Tools */}
      <section className="overviewSection">
        <h2 className="overviewSectionTitle">MCP Tool Layer</h2>
        <p className="overviewSectionSub">
          The LLM calls these tools in a loop (max 6 iterations) to resolve, book, and confirm appointments.
        </p>
        <div className="overviewToolGrid">
          {MCP_TOOLS.map((t) => (
            <div key={t.name} className="overviewToolCard surfaceCard">
              <span className={`overviewToolTag ${TAG_COLORS[t.tag]}`}>{t.tag}</span>
              <code className="overviewToolName">{t.name}</code>
            </div>
          ))}
        </div>
      </section>

      {/* Credential System */}
      <section className="overviewSection">
        <h2 className="overviewSectionTitle">Auto-Provisioned Credentials</h2>
        <p className="overviewSectionSub">
          Every doctor and admin gets login credentials generated deterministically on startup — no manual setup.
        </p>
        <div className="overviewCredGrid">
          <div className="overviewCredCard surfaceCard">
            <div className="overviewCredRole">Doctor</div>
            <code className="overviewCredEmail">dr.&#123;name&#125;@&#123;clinicslug&#125;.local</code>
            <code className="overviewCredPass">&#123;City&#125;_&#123;ClinicSlug&#125;_&#123;DoctorID&#125;</code>
            <div className="hint overviewCredEx">e.g. dr.rao@apolloclinicdelhi.local</div>
          </div>
          <div className="overviewCredCard surfaceCard">
            <div className="overviewCredRole">Admin</div>
            <code className="overviewCredEmail">admin@&#123;clinicslug&#125;.local</code>
            <code className="overviewCredPass">admin_&#123;ClinicSlug&#125;_&#123;Position&#125;</code>
            <div className="hint overviewCredEx">e.g. admin@apolloclinicdelhi.local</div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="overviewFooter">
        <p className="hint">
          Built by Peeyush Mishra &middot;{" "}
          <a href="https://github.com/Peeyush237" target="_blank" rel="noopener noreferrer">GitHub</a>
          {" "}&middot;{" "}
          <a href="https://www.linkedin.com/in/peeyush-mishra-23187027b" target="_blank" rel="noopener noreferrer">LinkedIn</a>
        </p>
      </footer>
    </div>
  );
}
