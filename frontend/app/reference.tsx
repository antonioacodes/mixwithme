"use client";
import { useEffect, useState } from "react";
import { Track, Version } from "./types";
const labels: Record<string, string> = {
  frequencies: "Frequências",
  dynamics: "Dinâmica",
  stereo: "Estéreo",
  clarity: "Clareza · descritores",
  transients: "Transientes",
};
type Comparison = {
  scores: {
    category: string;
    score: number | null;
    coverage: string;
    reason: string;
    components: { metric: string; delta: number; scale: number }[];
  }[];
  frequency_differences: {
    band: string;
    delta_db: number;
    recommendation: string;
  }[];
  warning: string;
  listening_gain_db: number | null;
  duration_difference_s: number;
};
export function Reference({
  version,
  tracks,
  api,
}: {
  version: Version;
  tracks: Track[];
  api: (path: string, init?: RequestInit) => Promise<Response>;
}) {
  const [track, setTrack] = useState(version.track_id);
  const [versions, setVersions] = useState<Version[]>([]);
  const [ref, setRef] = useState("");
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    setVersions([]);
    setRef("");
    setComparison(null);
    setError("");
    api(`/tracks/${track}/versions`)
      .then((r) => r.json())
      .then((v) => {
        if (alive) setVersions(v);
      })
      .catch((e) => {
        if (alive) setError(String(e));
      });
    return () => {
      alive = false;
    };
  }, [track, api]);
  return (
    <section className="panel">
      <span className="eyebrow">REFERÊNCIA ESCOLHIDA POR VOCÊ</span>
      <h3>Cinco notas de proximidade</h3>
      <p>
        100 significa descritores semelhantes à referência, não uma mix
        perfeita. Cadastre a referência como outra música e envie seu WAV pelo
        fluxo normal; ela também conta nos limites da biblioteca.
      </p>
      <div className="button-row">
        <label>
          Música de referência
          <select
            disabled={busy}
            value={track}
            onChange={(e) => setTrack(e.target.value)}
          >
            {tracks.map((t) => (
              <option value={t.id} key={t.id}>
                {t.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Versão de referência
          <select
            disabled={busy}
            value={ref}
            onChange={(e) => {
              setRef(e.target.value);
              setComparison(null);
            }}
          >
            <option value="">Selecione uma versão analisada</option>
            {versions
              .filter((v) => v.id !== version.id && v.status === "done")
              .map((v) => (
                <option value={v.id} key={v.id}>
                  {v.label}
                </option>
              ))}
          </select>
        </label>
        <button
          disabled={!ref || busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            setComparison(null);
            try {
              setComparison(
                await (
                  await api(`/versions/${version.id}/reference/${ref}`)
                ).json(),
              );
            } catch (e) {
              setError(String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Comparando…" : "Calcular proximidade"}
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {comparison && (
        <>
          <p className="notice">{comparison.warning}</p>
          <p>
            Diferença de duração: {comparison.duration_difference_s.toFixed(2)}{" "}
            s. Ajuste de escuta sugerido na DAW:{" "}
            {comparison.listening_gain_db?.toFixed(2) ?? "—"} dB na versão atual
            para igualar o LUFS integrado da referência. Não aplicado ao áudio.
          </p>
          <div className="scores">
            {comparison.scores.map((s) => (
              <article className="panel" key={s.category}>
                <span>{labels[s.category]}</span>
                <strong>
                  {s.score ?? "—"}
                  <small>/100</small>
                </strong>
                <p>Cobertura: {s.coverage} indicadores.</p>
                <details>
                  <summary>Fórmula e diferenças</summary>
                  <p>{s.reason}</p>
                  {s.components.map((p) => (
                    <p key={p.metric}>
                      {p.metric}: Δ {p.delta.toFixed(3)}; escala {p.scale}.
                    </p>
                  ))}
                </details>
              </article>
            ))}
          </div>
          {comparison.frequency_differences.map((d) => (
            <p key={d.band}>
              <b>
                {d.band}: {d.delta_db > 0 ? "+" : ""}
                {d.delta_db.toFixed(2)} dB de proporção espectral.
              </b>{" "}
              {d.recommendation}
            </p>
          ))}
        </>
      )}
    </section>
  );
}
