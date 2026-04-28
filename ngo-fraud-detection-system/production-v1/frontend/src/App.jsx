import { useEffect, useMemo, useState } from "react";
import {
  Download,
  FileDown,
  RefreshCw,
  Save,
  ShieldCheck,
  Upload
} from "lucide-react";
import { API_BASE, apiFetch } from "./api";
import { supabase } from "./supabaseClient";

const REVIEW_STATUSES = [
  "Pending Review",
  "Approved",
  "Rejected",
  "Needs Investigation",
  "Resolved"
];

const RISK_LEVELS = ["All", "High", "Medium", "Low"];

function getRole(user) {
  return user?.user_metadata?.role || user?.app_metadata?.role || "Viewer";
}

function isReviewer(role) {
  return role === "Admin" || role === "Reviewer";
}

function isAdmin(role) {
  return role === "Admin";
}

export default function App() {
  const [session, setSession] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stats, setStats] = useState(null);
  const [records, setRecords] = useState([]);
  const [batches, setBatches] = useState([]);
  const [weights, setWeights] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [drafts, setDrafts] = useState({});
  const [uploading, setUploading] = useState(false);

  const token = session?.access_token;
  const role = getRole(session?.user);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (token) {
      loadData();
    }
  }, [token]);

  async function loadData() {
    setError("");
    try {
      const [nextStats, nextRecords, nextBatches] = await Promise.all([
        apiFetch("/api/stats", { token }),
        apiFetch("/api/records?limit=250", { token }),
        apiFetch("/api/uploads", { token })
      ]);
      setStats(nextStats);
      setRecords(nextRecords);
      setBatches(nextBatches);
      setDrafts(
        Object.fromEntries(
          nextRecords.map((record) => [
            record.id,
            {
              review_status: record.review_status,
              reviewer_notes: record.reviewer_notes || ""
            }
          ])
        )
      );

      if (isAdmin(role)) {
        const [nextWeights, nextAudit] = await Promise.all([
          apiFetch("/api/settings/fraud-weights", { token }),
          apiFetch("/api/audit?limit=50", { token })
        ]);
        setWeights(nextWeights);
        setAuditLogs(nextAudit);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function signIn(event) {
    event.preventDefault();
    setError("");
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
    if (signInError) {
      setError(signInError.message);
    }
  }

  async function signOut() {
    await supabase.auth.signOut();
    setSession(null);
    setRecords([]);
    setBatches([]);
    setStats(null);
  }

  async function uploadCsv(event) {
    event.preventDefault();
    const file = event.currentTarget.elements.csv.files[0];
    if (!file) return;

    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      await apiFetch("/api/uploads", {
        token,
        method: "POST",
        body: formData
      });
      event.currentTarget.reset();
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function saveReview(recordId) {
    setError("");
    try {
      await apiFetch(`/api/records/${recordId}/review`, {
        token,
        method: "PATCH",
        body: drafts[recordId]
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function updateWeight(ruleKey, score) {
    setError("");
    try {
      await apiFetch(`/api/settings/fraud-weights/${ruleKey}`, {
        token,
        method: "PATCH",
        body: { score: Number(score) }
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function downloadPdf(batchId) {
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/reports/batches/${batchId}.pdf`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) {
        throw new Error("Unable to generate PDF report");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `fraud-summary-${batchId}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }

  const filteredRecords = useMemo(() => {
    return records.filter((record) => {
      const text = [
        record.beneficiary_id,
        record.full_name,
        record.phone,
        record.email,
        record.community,
        record.program_applied,
        record.risk_level,
        record.review_status,
        (record.fraud_flags || []).join(" ")
      ]
        .join(" ")
        .toLowerCase();
      const matchesSearch = !search || text.includes(search.toLowerCase());
      const matchesRisk = riskFilter === "All" || record.risk_level === riskFilter;
      const matchesStatus = statusFilter === "All" || record.review_status === statusFilter;
      return matchesSearch && matchesRisk && matchesStatus;
    });
  }, [records, search, riskFilter, statusFilter]);

  const riskCounts = useMemo(() => {
    return records.reduce(
      (acc, record) => {
        acc[record.risk_level] = (acc[record.risk_level] || 0) + 1;
        return acc;
      },
      { High: 0, Medium: 0, Low: 0 }
    );
  }, [records]);

  if (loading) {
    return <div className="centered">Loading...</div>;
  }

  if (!session) {
    return (
      <main className="login-shell">
        <section className="login-panel">
          <ShieldCheck size={34} />
          <h1>NGO Fraud & Beneficiary Integrity System</h1>
          <p>Production V1 reviewer portal</p>
          <form onSubmit={signIn}>
            <label>
              Email
              <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
            </label>
            <label>
              Password
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" required />
            </label>
            <button type="submit">Sign in</button>
            {error && <div className="error">{error}</div>}
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Production V1</p>
          <h1>NGO Fraud & Beneficiary Integrity System</h1>
        </div>
        <div className="user-box">
          <span>{session.user.email}</span>
          <strong>{role}</strong>
          <button className="ghost" onClick={signOut}>Sign out</button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="cards-grid">
        <MetricCard label="Total Records" value={stats?.total_records ?? 0} />
        <MetricCard label="High Risk" value={stats?.high_risk ?? 0} tone="high" />
        <MetricCard label="Medium Risk" value={stats?.medium_risk ?? 0} tone="medium" />
        <MetricCard label="Pending Review" value={stats?.pending_review ?? 0} />
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <h2>Risk Breakdown</h2>
            <p>Current scored records grouped by fraud risk level.</p>
          </div>
          <button className="ghost" onClick={loadData}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
        <RiskBars counts={riskCounts} total={records.length || 1} />
      </section>

      {isReviewer(role) && (
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>Batch Upload</h2>
              <p>Upload a beneficiary CSV for scoring and review.</p>
            </div>
          </div>
          <form className="upload-row" onSubmit={uploadCsv}>
            <input name="csv" type="file" accept=".csv" />
            <button type="submit" disabled={uploading}>
              <Upload size={16} /> {uploading ? "Uploading..." : "Upload CSV"}
            </button>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="section-header">
          <div>
            <h2>Upload History</h2>
            <p>Every uploaded file and its review load.</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Date</th>
                <th>Total</th>
                <th>High Risk</th>
                <th>Review Rate</th>
                <th>Uploaded By</th>
                <th>Report</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((batch) => (
                <tr key={batch.id}>
                  <td>{batch.file_name}</td>
                  <td>{new Date(batch.upload_date).toLocaleString()}</td>
                  <td>{batch.total_records}</td>
                  <td>{batch.high_risk_count}</td>
                  <td>{batch.review_rate}%</td>
                  <td>{batch.uploaded_by}</td>
                  <td>
                    {isReviewer(role) && (
                      <button className="icon-button" onClick={() => downloadPdf(batch.id)}>
                        <FileDown size={15} /> PDF
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <h2>Reviewer Queue</h2>
            <p>Search, filter, decide, and document each suspicious record.</p>
          </div>
          <button className="ghost" onClick={() => exportCsv(filteredRecords)}>
            <Download size={16} /> Export CSV
          </button>
        </div>
        <div className="filters">
          <input placeholder="Search name, phone, email, community, flag" value={search} onChange={(event) => setSearch(event.target.value)} />
          <select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value)}>
            {RISK_LEVELS.map((level) => <option key={level}>{level}</option>)}
          </select>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option>All</option>
            {REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Contact</th>
                <th>Program</th>
                <th>Score</th>
                <th>Risk</th>
                <th>Flags</th>
                <th>Status</th>
                <th>Reviewer Notes</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((record) => (
                <tr key={record.id}>
                  <td>
                    <strong>{record.full_name || "Unnamed"}</strong>
                    <span>{record.beneficiary_id}</span>
                  </td>
                  <td>
                    <div>{record.phone}</div>
                    <span>{record.email}</span>
                  </td>
                  <td>
                    <div>{record.program_applied}</div>
                    <span>{record.community}</span>
                  </td>
                  <td>
                    <div className="score-bar">
                      <span style={{ width: `${record.fraud_score}%` }} />
                    </div>
                    {record.fraud_score}/100
                  </td>
                  <td><RiskBadge risk={record.risk_level} /></td>
                  <td className="flags">{(record.fraud_flags || []).join("; ")}</td>
                  <td>
                    <select
                      disabled={!isReviewer(role)}
                      value={drafts[record.id]?.review_status || record.review_status}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [record.id]: {
                            ...current[record.id],
                            review_status: event.target.value
                          }
                        }))
                      }
                    >
                      {REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}
                    </select>
                  </td>
                  <td>
                    <textarea
                      disabled={!isReviewer(role)}
                      value={drafts[record.id]?.reviewer_notes || ""}
                      placeholder="Add reviewer notes"
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [record.id]: {
                            ...current[record.id],
                            reviewer_notes: event.target.value
                          }
                        }))
                      }
                    />
                  </td>
                  <td>
                    {isReviewer(role) && (
                      <button className="icon-button" onClick={() => saveReview(record.id)}>
                        <Save size={15} /> Save
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {isAdmin(role) && (
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>Fraud Weight Settings</h2>
              <p>Admin-configurable scoring weights used on future uploads.</p>
            </div>
          </div>
          <div className="weights-grid">
            {weights.map((weight) => (
              <label key={weight.rule_key}>
                <span>{weight.label}</span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  defaultValue={weight.score}
                  onBlur={(event) => updateWeight(weight.rule_key, event.target.value)}
                />
              </label>
            ))}
          </div>
        </section>
      )}

      {isAdmin(role) && (
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>Audit Log</h2>
              <p>Accountability trail for uploads, decisions, notes, and settings changes.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Actor</th>
                  <th>Role</th>
                  <th>Action</th>
                  <th>Record</th>
                  <th>Batch</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <tr key={log.id}>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td>{log.actor_email}</td>
                    <td>{log.actor_role}</td>
                    <td>{log.action}</td>
                    <td>{log.record_id || "-"}</td>
                    <td>{log.batch_id || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}

function MetricCard({ label, value, tone = "neutral" }) {
  return (
    <article className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function RiskBars({ counts, total }) {
  return (
    <div className="risk-bars">
      {["High", "Medium", "Low"].map((risk) => (
        <div key={risk}>
          <div className="bar-label">
            <span>{risk}</span>
            <strong>{counts[risk] || 0}</strong>
          </div>
          <div className={`risk-bar ${risk.toLowerCase()}`}>
            <span style={{ width: `${((counts[risk] || 0) / total) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function RiskBadge({ risk }) {
  return <span className={`risk-badge ${String(risk).toLowerCase()}`}>{risk}</span>;
}

function exportCsv(records) {
  const headers = [
    "beneficiary_id",
    "full_name",
    "phone",
    "email",
    "community",
    "program_applied",
    "fraud_score",
    "risk_level",
    "review_status",
    "reviewer_notes"
  ];
  const rows = records.map((record) =>
    headers.map((header) => JSON.stringify(record[header] ?? "")).join(",")
  );
  const blob = new Blob([[headers.join(","), ...rows].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "review-queue.csv";
  link.click();
  URL.revokeObjectURL(url);
}
