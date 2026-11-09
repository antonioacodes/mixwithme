"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Context, Mixer } from "./mixer";
import { Report, number } from "./report";
import { initialSession, Session, Track, Version } from "./types";

type Comparison = {
  changes: Record<
    string,
    { a: number | null; b: number | null; delta_b_minus_a: number | null }
  >;
  warning: string;
  duration_difference_s: number;
  same_engine: boolean;
};
export default function Home() {
  const [token, setToken] = useState("");
  const [entry, setEntry] = useState("");
  const [tracks, setTracks] = useState<Track[]>([]);
  const [tid, setTid] = useState("");
  const [session, setSession] = useState<Session>(initialSession);
  const [title, setTitle] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  const [vid, setVid] = useState("");
  const [selected, setSelected] = useState<Version | null>(null);
  const [tab, setTab] = useState("session");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [label, setLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [audio, setAudio] = useState("");
  const audioRef = useRef("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const api = useCallback(
    async (path: string, init: RequestInit = {}) => {
      const res = await fetch("/api" + path, {
        ...init,
        headers: { Authorization: "Bearer " + token, ...init.headers },
      });
      if (!res.ok) {
        let msg;
        try {
          const data = await res.json();
          msg =
            typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail);
        } catch {
          msg = `Erro ${res.status}`;
        }
        throw new Error(msg);
      }
      return res;
    },
    [token],
  );
  const refresh = useCallback(async () => {
    setTracks(await (await api("/tracks")).json());
  }, [api]);
  useEffect(() => {
    if (token)
      refresh().catch((e) => {
        setError(e.message);
        setToken("");
      });
  }, [token, refresh]);
  useEffect(() => {
    if (!tid || !token) return;
    let alive = true;
    const poll = async () => {
      try {
        const data = await (await api(`/tracks/${tid}/versions`)).json();
        if (alive) setVersions(data);
      } catch (e) {
        if (alive) setError(String(e));
      }
    };
    poll();
    const timer = setInterval(poll, 2500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [tid, token, api]);
  const status = versions.find((v) => v.id === vid)?.status;
  useEffect(() => {
    setSelected(null);
    setAudio("");
    if (audioRef.current) {
      URL.revokeObjectURL(audioRef.current);
      audioRef.current = "";
    }
    if (!vid || !token) return;
    let alive = true;
    api("/versions/" + vid)
      .then((r) => r.json())
      .then((v) => {
        if (alive) setSelected(v);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [vid, status, token, api]);
  useEffect(
    () => () => {
      if (audioRef.current) URL.revokeObjectURL(audioRef.current);
    },
    [],
  );
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const choose = (t: Track | null) => {
    if (dirty && !confirm("Descartar alterações ainda não salvas?")) return;
    setTid(t?.id || "");
    setTitle(t?.title || "");
    setSession(
      t ? structuredClone(t.session) : structuredClone(initialSession),
    );
    setDirty(false);
    setVersions([]);
    setVid("");
    setComparison(null);
    setCompareIds([]);
    setTab("session");
    setNotice("");
    setFile(null);
    setLabel("");
  };
  const edit = (s: Session) => {
    setSession(s);
    setDirty(true);
  };
  const save = () =>
    run(async () => {
      if (tid) {
        await api(`/tracks/${tid}/session`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(session),
        });
      } else {
        const t = await (
          await api("/tracks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, session }),
          })
        ).json();
        setTid(t.id);
      }
      setDirty(false);
      await refresh();
      setNotice(
        "Sessão salva. Próximos uploads usarão este contexto; versões anteriores preservam o original.",
      );
    });
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a href="/" className="brand">
          <span className="brand-mark">Ⅲ</span>mixwithme
          <span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">
          PERSONAL STUDIO <span>TRAP</span>
        </div>
        <button className="new-track" onClick={() => choose(null)}>
          ＋ Nova música
        </button>
        <span className="nav-label">BIBLIOTECA</span>
        <nav>
          {tracks.map((t) => (
            <button
              className={t.id === tid ? "active" : ""}
              key={t.id}
              onClick={() => choose(t)}
            >
              <span>♫</span>
              {t.title}
              <span>↗</span>
            </button>
          ))}
          {tracks.length === 0 && (
            <p className="muted empty-nav">
              Suas músicas e versões aparecem aqui.
            </p>
          )}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> Análise local · CPU
          <p>Ouça. Meça. Investigue.</p>
          {token && (
            <button
              className="subtle"
              onClick={() => {
                setToken("");
                setTracks([]);
                setTid("");
                setVid("");
                setVersions([]);
                setSelected(null);
                setAudio("");
                setEntry("");
              }}
            >
              Bloquear sessão
            </button>
          )}
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            WORKSPACE <b>/</b> {tid ? title : "Nova música"}
          </span>
          <span className="badge">PROTÓTIPO 0.1</span>
        </header>
        <div className="content">
          <div className="hero">
            <div>
              <span className="eyebrow">MIX / MASTER LAB</span>
              <h1>
                Mais contexto.
                <br />
                <em>Melhores decisões.</em>
              </h1>
              <p>
                Conheça os números da sua mix. Investigue as hipóteses.
                <br />A decisão final continua nos seus ouvidos.
              </p>
            </div>
            <div className="hero-art" aria-hidden="true">
              {[
                22, 42, 31, 61, 95, 53, 80, 118, 76, 46, 86, 135, 102, 62, 92,
                55, 35, 71, 48, 25,
              ].map((h, i) => (
                <i key={i} style={{ height: h }} />
              ))}
            </div>
          </div>
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              {notice}
            </div>
          )}
          {!token ? (
            <form
              className="panel login"
              onSubmit={(e) => {
                e.preventDefault();
                setError("");
                setToken(entry);
                setEntry("");
              }}
            >
              <span className="eyebrow">SEU ESTÚDIO PRIVADO</span>
              <h2>Entre no laboratório.</h2>
              <p>
                Use a chave de acesso configurada no servidor. Ela fica apenas
                na memória desta aba.
              </p>
              <label>
                Chave de acesso
                <input
                  type="password"
                  autoComplete="off"
                  required
                  value={entry}
                  onChange={(e) => setEntry(e.target.value)}
                />
              </label>
              <button className="primary">Desbloquear →</button>
            </form>
          ) : (
            <>
              <div className="tabs" role="tablist" aria-label="Área da música">
                {[
                  ["session", "Sessão & mixer"],
                  ["analysis", "Versões & análise"],
                  ["compare", "Comparar versões"],
                ].map(([id, name]) => (
                  <button
                    role="tab"
                    aria-selected={tab === id}
                    key={id}
                    onClick={() => setTab(id)}
                  >
                    {name}
                  </button>
                ))}
              </div>
              {tab === "session" && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void save();
                  }}
                >
                  <div className="section-heading">
                    <label className="track-name">
                      Nome da música
                      <input
                        required
                        disabled={!!tid}
                        value={title}
                        maxLength={120}
                        placeholder="Ex.: Diamonds"
                        onChange={(e) => {
                          setTitle(e.target.value);
                          setDirty(true);
                        }}
                      />
                    </label>
                    <button className="primary" disabled={busy}>
                      {busy
                        ? "Salvando…"
                        : tid
                          ? "Salvar sessão"
                          : "Criar música"}{" "}
                      →
                    </button>
                  </div>
                  <Context session={session} onChange={edit} />
                  <Mixer session={session} onChange={edit} />
                  <div className="save-footer">
                    <span className="muted">
                      {dirty
                        ? "Alterações ainda não salvas."
                        : "Contexto pronto para revisar."}{" "}
                      Parâmetros dos plugins não são obrigatórios.
                    </span>
                    <button className="primary" disabled={busy}>
                      Salvar sessão →
                    </button>
                  </div>
                </form>
              )}
              {tab === "analysis" && (
                <>
                  {!tid ? (
                    <div className="panel empty">
                      <h2>Comece pela sessão.</h2>
                      <p>
                        Crie uma música e preencha o contexto antes de enviar
                        seu WAV.
                      </p>
                      <button onClick={() => setTab("session")}>
                        Configurar sessão
                      </button>
                    </div>
                  ) : (
                    <>
                      <form
                        className="panel upload"
                        onSubmit={(e) => {
                          e.preventDefault();
                          void run(async () => {
                            if (!file) throw new Error("Selecione um WAV.");
                            if (file.size > 250 * 1024 * 1024)
                              throw new Error("Limite de 250 MiB por WAV.");
                            const v = await (
                              await api(
                                `/tracks/${tid}/versions?label=${encodeURIComponent(label || file.name)}`,
                                {
                                  method: "POST",
                                  headers: { "Content-Type": "audio/wav" },
                                  body: file,
                                },
                              )
                            ).json();
                            setVid(v.id);
                            setFile(null);
                            if (fileInputRef.current)
                              fileInputRef.current.value = "";
                            setLabel("");
                            setVersions(
                              await (
                                await api(`/tracks/${tid}/versions`)
                              ).json(),
                            );
                            setNotice(
                              "WAV recebido. A análise está na fila local.",
                            );
                          });
                        }}
                      >
                        <div>
                          <span className="eyebrow">
                            NOVA VERSÃO · {versions.length}/5
                          </span>
                          <h2>Traga sua próxima mix.</h2>
                          <p className="muted">
                            WAV mono/estéreo · 16/24 bit PCM ou 32 float · 1
                            s–10 min · até 250 MiB
                          </p>
                        </div>
                        <label>
                          Nome da versão
                          <input
                            maxLength={80}
                            value={label}
                            placeholder="Ex.: v2 — ajuste do vocal"
                            onChange={(e) => setLabel(e.target.value)}
                          />
                        </label>
                        <label>
                          Arquivo WAV
                          <input
                            ref={fileInputRef}
                            type="file"
                            accept=".wav,audio/wav"
                            required
                            onChange={(e) =>
                              setFile(e.target.files?.[0] || null)
                            }
                          />
                        </label>
                        <button
                          className="primary"
                          disabled={busy || dirty || versions.length >= 5}
                        >
                          {busy ? "Enviando…" : "Enviar & analisar →"}
                        </button>
                        {dirty && (
                          <p className="notice">
                            Salve as alterações da sessão antes de enviar.
                          </p>
                        )}
                      </form>
                      <div className="version-list">
                        {versions.map((v) => (
                          <button
                            key={v.id}
                            className={v.id === vid ? "selected" : ""}
                            onClick={() => setVid(v.id)}
                          >
                            <span>{v.label}</span>
                            <small>
                              {new Date(v.created_at).toLocaleString("pt-BR")} ·{" "}
                              {
                                (
                                  {
                                    done: "Analisada",
                                    queued: "Na fila",
                                    running: "Analisando",
                                    uploading: "Enviando",
                                    failed: "Falhou",
                                  } as Record<string, string>
                                )[v.status]
                              }
                            </small>
                          </button>
                        ))}
                      </div>
                      {selected && (
                        <>
                          <div className="section-heading">
                            <h2>{selected.label}</h2>
                            <div className="button-row">
                              <button
                                disabled={
                                  busy || selected.status === "uploading"
                                }
                                onClick={() =>
                                  void run(async () => {
                                    const blob = await (
                                      await api(
                                        `/versions/${selected.id}/audio`,
                                      )
                                    ).blob();
                                    if (audioRef.current)
                                      URL.revokeObjectURL(audioRef.current);
                                    audioRef.current =
                                      URL.createObjectURL(blob);
                                    setAudio(audioRef.current);
                                  })
                                }
                              >
                                Carregar áudio
                              </button>
                              <button
                                className="danger subtle"
                                disabled={
                                  busy ||
                                  ["uploading", "running"].includes(
                                    selected.status,
                                  )
                                }
                                onClick={() => {
                                  if (
                                    confirm(
                                      "Excluir este WAV, análise e respostas permanentemente?",
                                    )
                                  )
                                    void run(async () => {
                                      await api(`/versions/${selected.id}`, {
                                        method: "DELETE",
                                      });
                                      setVid("");
                                      setVersions(
                                        await (
                                          await api(`/tracks/${tid}/versions`)
                                        ).json(),
                                      );
                                    });
                                }}
                              >
                                Excluir versão
                              </button>
                            </div>
                          </div>
                          {audio && <audio src={audio} controls />}
                          {selected.error && (
                            <p className="notice error">{selected.error}</p>
                          )}
                          {selected.status === "done" && selected.result ? (
                            <Report
                              key={selected.id}
                              version={selected}
                              saveAnswer={async (question_id, answer) => {
                                await api(`/versions/${selected.id}/answers`, {
                                  method: "POST",
                                  headers: {
                                    "Content-Type": "application/json",
                                  },
                                  body: JSON.stringify({ question_id, answer }),
                                });
                                setSelected(
                                  await (
                                    await api("/versions/" + selected.id)
                                  ).json(),
                                );
                              }}
                            />
                          ) : (
                            !selected.error && (
                              <div className="panel empty">
                                <h3>
                                  {selected.status === "running"
                                    ? "Medindo o WAV…"
                                    : "Aguardando o worker local…"}
                                </h3>
                                <p>
                                  A página acompanha o status automaticamente.
                                </p>
                              </div>
                            )
                          )}
                        </>
                      )}
                      {versions.length === 0 && (
                        <p className="empty muted">
                          Cada versão preserva seu WAV, contexto, medições e
                          investigação.
                        </p>
                      )}
                    </>
                  )}
                </>
              )}
              {tab === "compare" && (
                <div className="panel">
                  <span className="eyebrow">A / B</span>
                  <h2>O que mudou entre versões?</h2>
                  <p className="muted">
                    Selecione duas versões analisadas, na ordem A e B. Valores
                    originais, sem normalização.
                  </p>
                  {versions
                    .filter((v) => v.status === "done")
                    .map((v) => (
                      <label className="compare-choice checkbox" key={v.id}>
                        <input
                          type="checkbox"
                          checked={compareIds.includes(v.id)}
                          disabled={
                            !compareIds.includes(v.id) &&
                            compareIds.length === 2
                          }
                          onChange={() => {
                            setComparison(null);
                            setCompareIds(
                              compareIds.includes(v.id)
                                ? compareIds.filter((id) => id !== v.id)
                                : [...compareIds, v.id],
                            );
                          }}
                        />
                        {compareIds.includes(v.id)
                          ? `${compareIds.indexOf(v.id) === 0 ? "A" : "B"} · `
                          : ""}
                        {v.label}
                      </label>
                    ))}
                  <button
                    className="primary"
                    disabled={busy || compareIds.length !== 2}
                    onClick={() =>
                      void run(async () => {
                        setComparison(
                          await (
                            await api(
                              `/tracks/${tid}/compare?a=${compareIds[0]}&b=${compareIds[1]}`,
                            )
                          ).json(),
                        );
                      })
                    }
                  >
                    Comparar →
                  </button>
                  {comparison && (
                    <>
                      <p className="notice">{comparison.warning}</p>
                      <p className="muted">
                        Diferença de duração:{" "}
                        {number(comparison.duration_difference_s)} s.{" "}
                        {comparison.same_engine
                          ? "Mesma versão do motor."
                          : "Atenção: motores de análise diferentes."}
                      </p>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Medição</th>
                              <th>A</th>
                              <th>B</th>
                              <th>Δ B − A</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(comparison.changes).map(
                              ([k, v]) => (
                                <tr key={k}>
                                  <td>{k}</td>
                                  <td>{number(v.a)}</td>
                                  <td>{number(v.b)}</td>
                                  <td>{number(v.delta_b_minus_a)}</td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}
            </>
          )}
          <footer>
            MixWithMe <span>Feito para investigar. Não para adivinhar.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
