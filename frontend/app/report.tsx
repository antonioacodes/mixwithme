"use client";
import { useState } from "react";
import { Version, Track } from "./types";
import { Reference } from "./reference";
export const number = (v: unknown) =>
  typeof v === "number" ? v.toFixed(2) : "—";
export function Report({
  version,
  saveAnswer,
  tracks,
  api,
}: {
  version: Version;
  tracks: Track[];
  api: (path: string, init?: RequestInit) => Promise<Response>;
  saveAnswer: (question: string, answer: string) => Promise<void>;
}) {
  const [history, setHistory] = useState<
    | { created_at: string; result: Version["result"]; answers: unknown[] }[]
    | null
  >(null);
  const [historyError, setHistoryError] = useState("");
  const r = version.result!;
  type Segment = {
    start_s: number;
    end_s: number;
    active: boolean;
    rms_dbfs: number | null;
    crest_db: number | null;
    centroid_hz: number | null;
    flatness: number | null;
    contrast_db: number | null;
    low_band_crest_db: number | null;
    bands: Record<
      string,
      {
        energy_pct: number | null;
        correlation: number | null;
        side_pct: number | null;
      }
    >;
  };
  const timeline = (r.metrics.timeline || []) as Segment[];
  const [second, setSecond] = useState(0);
  const segment = timeline[second];
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
          ["LUFS integrado", r.metrics.integrated_lufs, "LUFS"],
          ["True peak", r.metrics.true_peak_dbtp, "dBTP"],
          ["Loudness range", r.metrics.lra_lu, "LU"],
          ["Pico / loudness", r.metrics.peak_to_loudness_db, "dB"],
          ["Sample peak", r.metrics.sample_peak_dbfs, "dBFS"],
          ["RMS sem ponderação", r.metrics.rms_dbfs, "dBFS"],
          ["Crest factor", r.metrics.crest_db, "dB"],
          ["Correlação L/R", r.metrics.lr_correlation, "−1 a +1"],
        ].map(([label, value, unit]) => (
          <div className="metric" key={String(label)}>
            <span>{String(label)}</span>
            <strong>
              {number(value)} <small>{String(unit)}</small>
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
      {timeline.length > 0 && (
        <>
          <section className="panel">
            <span className="eyebrow">AO LONGO DA MÚSICA</span>
            <h3>Localize o trecho antes de ajustar</h3>
            <label>
              Segundo {segment?.start_s}
              <input
                type="range"
                min={0}
                max={timeline.length - 1}
                value={second}
                onChange={(e) => setSecond(Number(e.target.value))}
              />
            </label>
            {segment && (
              <>
                <p>
                  {number(segment.start_s)}–{number(segment.end_s)} s · RMS{" "}
                  {number(segment.rms_dbfs)} dBFS · crest{" "}
                  {number(segment.crest_db)} dB · centroide{" "}
                  {number(segment.centroid_hz)} Hz.
                </p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Faixa</th>
                        <th>Energia %</th>
                        <th>Correlação</th>
                        <th>Side %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(segment.bands).map(([band, v]) => (
                        <tr key={band}>
                          <td>{band}</td>
                          <td>{number(v.energy_pct)}</td>
                          <td>{number(v.correlation)}</td>
                          <td>{number(v.side_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
          <section className="panel">
            <h3>Clareza e ataques: indicadores do mix completo</h3>
            <div className="metrics">
              {[
                ["Contraste espectral", r.metrics.spectral_contrast_db, "dB"],
                ["Planicidade espectral", r.metrics.spectral_flatness, "0–1"],
                ["Centroide", r.metrics.spectral_centroid_hz, "Hz"],
                ["Subida mediana", r.metrics.attack_median_ms, "ms"],
                [
                  "Contraste local dos ataques",
                  r.metrics.attack_contrast_median_db,
                  "dB",
                ],
                [
                  "Crest de 40–250 Hz",
                  r.metrics.low_band_crest_median_db,
                  "dB",
                ],
                [
                  "Eventos detectados",
                  r.metrics.transient_event_count,
                  "eventos",
                ],
                ["Densidade de ataques", r.metrics.onsets_per_second, "/s"],
              ].map(([label, value, unit]) => (
                <div className="metric" key={String(label)}>
                  <span>{String(label)}</span>
                  <strong>
                    {number(value)} <small>{String(unit)}</small>
                  </strong>
                </div>
              ))}
            </div>
            <p className="muted">
              Esses descritores não isolam voz, kick ou snare. Contraste
              espectral não prova separação entre instrumentos, e um ataque
              rápido não é necessariamente melhor.
            </p>
          </section>
          <details className="panel">
            <summary>
              Eventos de ataque detectados (
              {String(r.metrics.transient_event_count ?? 0)})
            </summary>
            <p>
              Resolução de 10 ms. Exibidos até 200 eventos; a contagem total
              inclui todos. Não identifica instrumentos.
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Tempo</th>
                    <th>Subida</th>
                    <th>Contraste local</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    (r.metrics.transient_events || []) as {
                      time_s: number;
                      attack_ms: number;
                      contrast_db: number;
                    }[]
                  ).map((e, i) => (
                    <tr key={i}>
                      <td>{number(e.time_s)} s</td>
                      <td>{number(e.attack_ms)} ms</td>
                      <td>{number(e.contrast_db)} dB</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <Reference
            key={version.id}
            version={version}
            tracks={tracks}
            api={api}
          />
          {r.checks && r.checks.length > 0 && (
            <section className="panel">
              <span className="eyebrow">CHECKS TÉCNICOS</span>
              <h3>Medição, evidência e próximo passo</h3>
              <p>Esses estados não são uma nota de qualidade. Eles mostram o que foi medido e o que ainda depende do destino ou da escuta.</p>
              <div className="hypotheses">
                {r.checks.map((check) => (
                  <article className="panel" key={check.id}>
                    <span className={`badge check-${check.status}`}>{check.status}</span>
                    <h3>{check.label}</h3>
                    <p className="evidence">{check.evidence}</p>
                    <p>{check.next_step}</p>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}
      {!timeline.length && (
        <p className="notice">
          Relatório do motor anterior. Use “Reanalisar WAV” para obter as novas
          medições; as notas antigas de 100 foram retiradas desta tela.
        </p>
      )}
      <h3>Investigar antes de concluir</h3>
      <div className="hypotheses">
        {r.hypotheses.map((h) => (
          <article className="panel" key={h.id}>
            <span className="badge">
              Hipótese · confiança{" "}
              {h.confidence === "medium" ? "moderada" : "baixa"}
            </span>
            <h3>{h.hypothesis}</h3>
            <p className="evidence">Evidência: {h.evidence}</p>
            {h.start_s != null && (
              <button
                className="subtle"
                onClick={() =>
                  setSecond(
                    Math.min(
                      timeline.length - 1,
                      Math.max(0, Math.floor(h.start_s!)),
                    ),
                  )
                }
              >
                Examinar {number(h.start_s)} s na tabela acima
              </button>
            )}
            {h.recommendation && (
              <p>
                <b>Teste sugerido:</b> {h.recommendation}
              </p>
            )}
            {!!h.declared_plugins?.length && (
              <p className="muted">
                Plugins declarados para investigar:{" "}
                {h.declared_plugins.join(" · ")}. Não foram medidos
                isoladamente.
              </p>
            )}
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
      <section className="panel">
        <h3>Histórico de análises deste WAV</h3>
        <button
          onClick={async () => {
            setHistoryError("");
            try {
              setHistory(
                await (
                  await api(`/versions/${version.id}/analysis-history`)
                ).json(),
              );
            } catch (e) {
              setHistoryError(String(e));
            }
          }}
        >
          Ver relatórios anteriores
        </button>
        {historyError && <p role="alert">{historyError}</p>}
        {history && history.length === 0 && <p>Nenhuma reanálise anterior.</p>}
        {history?.map((h, i) => (
          <details key={i}>
            <summary>
              {h.created_at} · {h.result?.engine}
            </summary>
            <pre>{JSON.stringify(h, null, 2)}</pre>
          </details>
        ))}
      </section>
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
