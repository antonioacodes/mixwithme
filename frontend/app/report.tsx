"use client";
import { useState } from "react";
import { Version } from "./types";
export const number = (v: unknown) =>
  typeof v === "number" ? v.toFixed(2) : "—";
const labels: Record<string, string> = {
  frequencies: "Frequências",
  dynamics: "Dinâmica",
  stereo: "Estéreo",
  clarity: "Clareza",
  transients: "Transientes",
};
export function Report({
  version,
  saveAnswer,
}: {
  version: Version;
  saveAnswer: (question: string, answer: string) => Promise<void>;
}) {
  const r = version.result!;
  return (
    <div className="report">
      <div className="section-heading">
        <div>
          <span className="eyebrow">03 / ANÁLISE · {r.engine}</span>
          <h2>O que o arquivo nos diz.</h2>
        </div>
        <span className="badge amber">Diagnóstico provisório</span>
      </div>
      <div className="metrics">
        {[
          ["Sample peak", r.metrics.sample_peak_dbfs, "dBFS"],
          ["RMS sem ponderação", r.metrics.rms_dbfs, "dBFS"],
          ["Crest factor", r.metrics.crest_db, "dB"],
          ["Correlação L/R", r.metrics.lr_correlation, "−1 a +1"],
        ].map(([label, value, unit]) => (
          <div className="metric" key={String(label)}>
            <span>{label}</span>
            <strong>
              {number(value)} <small>{unit}</small>
            </strong>
          </div>
        ))}
      </div>
      <div className="analysis-grid">
        <div className="panel">
          <span className="eyebrow">ENERGIA ESPECTRAL</span>
          <h3>Distribuição, sem curva ideal.</h3>
          <div className="bands">
            {Object.entries(r.metrics.band_energy_pct).map(([band, value]) => (
              <div className="band" key={band}>
                <span>{band.replace("_", " ")}</span>
                <div>
                  <i style={{ width: `${value || 0}%` }} />
                </div>
                <b>{number(value)}%</b>
              </div>
            ))}
          </div>
          <p className="muted">
            Percentual da potência espectral total; soma pode ser menor que 100%
            (DC, &lt;20 Hz e &gt;20 kHz). Não mede o volume percebido de cada
            instrumento.
          </p>
        </div>
        <div className="panel">
          <span className="eyebrow">ENVELOPE DE ENERGIA</span>
          <h3>RMS por segundo.</h3>
          <svg
            className="envelope"
            viewBox="0 0 600 140"
            role="img"
            aria-label="RMS não ponderado por segundo, escala de menos 80 a zero dBFS"
          >
            <line x1="0" x2="600" y1="139" y2="139" stroke="#37423e" />
            <polyline
              fill="none"
              stroke="#b5f66b"
              strokeWidth="2"
              points={r.metrics.window_rms_dbfs
                .map(
                  (v, i) =>
                    `${(i * 600) / Math.max(1, r.metrics.window_rms_dbfs.length - 1)},${140 - (Math.max(-80, Math.min(0, v ?? -80)) + 80) * 1.75}`,
                )
                .join(" ")}
            />
          </svg>
          <p className="muted">
            {number(r.metrics.duration_s)} s · {r.metrics.sample_rate_hz} Hz ·{" "}
            {r.metrics.subtype} · {r.metrics.channels} canal(is). Escala: −80 a
            0 dBFS, sem normalização.
          </p>
        </div>
      </div>
      <h3>Triagem por dimensão</h3>
      <p className="muted">
        Estas notas provisórias sinalizam verificações específicas. Não são
        notas de qualidade musical e não formam uma média geral.
      </p>
      <div className="scores">
        {r.scores.map((s) => (
          <article className="panel" key={s.category}>
            <span>{labels[s.category]}</span>
            <strong>
              {s.score ?? "—"}
              {s.score !== null && <small>/100</small>}
            </strong>
            <p>{s.reason}</p>
          </article>
        ))}
      </div>
      <h3>Investigar antes de concluir</h3>
      <div className="hypotheses">
        {r.hypotheses.map((h) => (
          <article className="panel" key={h.id}>
            <span className="badge">Hipótese · confiança baixa</span>
            <h3>{h.hypothesis}</h3>
            <p className="evidence">Evidência: {h.evidence}</p>
            <Question
              key={h.id}
              question={h.question}
              saved={
                version.answers?.find((a) => a.question_id === h.id)?.answer
              }
              onSave={(answer) => saveAnswer(h.id, answer)}
            />
          </article>
        ))}
      </div>
      <div className="panel limits">
        <h3>Limites desta análise</h3>
        <ul>
          {r.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
        <p>
          As respostas ficam registradas como contexto humano. O protótipo não
          usa um LLM nem transforma relatos em conclusões automáticas.
        </p>
      </div>
      <details className="panel">
        <summary>Métodos, dados e contexto desta versão</summary>
        <dl>
          {Object.entries(r.methods).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        <p className="hash">SHA-256: {r.sha256}</p>
        <pre>
          {JSON.stringify(
            { metrics: r.metrics, session: version.session },
            null,
            2,
          )}
        </pre>
      </details>
    </div>
  );
}
function Question({
  question,
  saved,
  onSave,
}: {
  question: string;
  saved?: string;
  onSave: (answer: string) => Promise<void>;
}) {
  const [answer, setAnswer] = useState(saved || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          await onSave(answer);
        } catch (e) {
          setError(String(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <label>
        {question}
        <textarea
          value={answer}
          maxLength={2000}
          required
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Sua observação ou ‘não sei’"
        />
      </label>
      <div className="button-row">
        <button disabled={busy}>
          {busy
            ? "Salvando…"
            : saved
              ? "Atualizar resposta"
              : "Registrar resposta"}
        </button>
        <button
          type="button"
          className="subtle"
          onClick={() => setAnswer("Não sei")}
        >
          Não sei
        </button>
        {saved && (
          <span className="muted">Resposta registrada nesta versão</span>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
