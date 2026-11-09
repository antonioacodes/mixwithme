"use client";
import { Channel, Plugin, Session } from "./types";
import { RoutingGraph } from "./routing-graph";

export function Mixer({
  session,
  onChange,
}: {
  session: Session;
  onChange: (s: Session) => void;
}) {
  const update = (id: string, patch: Partial<Channel>) =>
    onChange({
      ...session,
      channels: session.channels.map((c) =>
        c.id === id ? { ...c, ...patch } : c,
      ),
    });
  const add = () => {
    const id = crypto.randomUUID().replaceAll("-", "");
    onChange({
      ...session,
      channels: [
        ...session.channels,
        {
          id,
          name: "Novo canal",
          kind: "backing",
          fader_db: 0,
          pan: 0,
          width: 1,
          plugins: [],
        },
      ],
      routes: [
        ...session.routes,
        {
          source: id,
          target: session.channels.find((c) => c.kind === "master")!.id,
          kind: "output",
          gain_db: 0,
        },
      ],
    });
  };
  return (
    <>
      <div className="section-heading">
        <div>
          <span className="eyebrow">02 / SESSÃO DECLARADA</span>
          <h2>Seu mixer, em contexto.</h2>
        </div>
        <button
          type="button"
          onClick={add}
          disabled={session.channels.length >= 64}
        >
          ＋ Adicionar canal
        </button>
      </div>
      <p className="muted">
        Registre a posição dos controles da DAW. Estes faders não modificam nem
        reproduzem o WAV.
      </p>
      <div className="mixer">
        {session.channels.map((c, index) => (
          <article className={"strip " + c.kind} key={c.id}>
            <div className="strip-number">
              {String(index + 1).padStart(2, "0")} <span>{c.kind}</span>
            </div>
            <input
              aria-label={`Nome do canal ${index + 1}`}
              value={c.name}
              maxLength={80}
              required
              onChange={(e) => update(c.id, { name: e.target.value })}
            />
            {c.kind !== "master" && (
              <select
                aria-label={`Tipo de ${c.name}`}
                value={c.kind}
                onChange={(e) =>
                  update(c.id, { kind: e.target.value as Channel["kind"] })
                }
              >
                {[
                  "vocal",
                  "backing",
                  "adlib",
                  "beat",
                  "bus",
                  "return",
                  "other",
                ].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            )}
            <label className="fader-label">
              Fader <strong>{c.fader_db.toFixed(1)} dB</strong>
              <input
                className="fader"
                type="range"
                min="-60"
                max="12"
                step="0.1"
                value={c.fader_db}
                onChange={(e) => update(c.id, { fader_db: +e.target.value })}
              />
            </label>
            <label>
              Pan{" "}
              <span>
                {c.pan === 0
                  ? "C"
                  : `${Math.round(Math.abs(c.pan) * 100)} ${c.pan < 0 ? "L" : "R"}`}
              </span>
              <input
                type="range"
                min="-1"
                max="1"
                step=".01"
                value={c.pan}
                onChange={(e) => update(c.id, { pan: +e.target.value })}
              />
            </label>
            <label>
              Largura <span>{Math.round(c.width * 100)}%</span>
              <input
                type="range"
                min="0"
                max="2"
                step=".01"
                value={c.width}
                onChange={(e) => update(c.id, { width: +e.target.value })}
              />
            </label>
            <details>
              <summary>
                Plugins <span>{c.plugins.length}</span>
              </summary>
              <div className="plugin-list">
                {c.plugins.map((p, i) => (
                  <div className="plugin" key={i}>
                    <input
                      aria-label={`Plugin ${i + 1} de ${c.name}`}
                      placeholder="Nome do plugin"
                      value={p.name}
                      maxLength={100}
                      required
                      onChange={(e) =>
                        update(c.id, {
                          plugins: c.plugins.map((x, j) =>
                            i === j ? { ...x, name: e.target.value } : x,
                          ),
                        })
                      }
                    />
                    <select
                      aria-label={`Função de ${p.name}`}
                      value={p.kind}
                      onChange={(e) =>
                        update(c.id, {
                          plugins: c.plugins.map((x, j) =>
                            i === j
                              ? { ...x, kind: e.target.value as Plugin["kind"] }
                              : x,
                          ),
                        })
                      }
                    >
                      {[
                        "eq",
                        "compressor",
                        "limiter",
                        "reverb",
                        "delay",
                        "saturation",
                        "other",
                      ].map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={p.bypass}
                        onChange={(e) =>
                          update(c.id, {
                            plugins: c.plugins.map((x, j) =>
                              i === j ? { ...x, bypass: e.target.checked } : x,
                            ),
                          })
                        }
                      />
                      Bypass
                    </label>
                    <div className="button-row">
                      <button
                        type="button"
                        aria-label={`Subir ${p.name}`}
                        disabled={i === 0}
                        onClick={() => {
                          const a = [...c.plugins];
                          [a[i - 1], a[i]] = [a[i], a[i - 1]];
                          update(c.id, { plugins: a });
                        }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        aria-label={`Descer ${p.name}`}
                        disabled={i === c.plugins.length - 1}
                        onClick={() => {
                          const a = [...c.plugins];
                          [a[i + 1], a[i]] = [a[i], a[i + 1]];
                          update(c.id, { plugins: a });
                        }}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        aria-label={`Remover ${p.name}`}
                        onClick={() =>
                          update(c.id, {
                            plugins: c.plugins.filter((_, j) => j !== i),
                          })
                        }
                      >
                        ×
                      </button>
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  className="subtle"
                  disabled={c.plugins.length >= 30}
                  onClick={() =>
                    update(c.id, {
                      plugins: [
                        ...c.plugins,
                        { name: "Novo plugin", kind: "other", bypass: false },
                      ],
                    })
                  }
                >
                  ＋ Plugin
                </button>
              </div>
            </details>
            {c.kind !== "master" && (
              <>
                <label>
                  Saída
                  <select
                    value={
                      session.routes.find(
                        (r) => r.source === c.id && r.kind === "output",
                      )?.target || ""
                    }
                    onChange={(e) =>
                      onChange({
                        ...session,
                        routes: session.routes.map((r) =>
                          r.source === c.id && r.kind === "output"
                            ? { ...r, target: e.target.value }
                            : r,
                        ),
                      })
                    }
                  >
                    {session.channels
                      .filter((x) => x.id !== c.id)
                      .map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.name}
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="subtle danger"
                  onClick={() =>
                    onChange({
                      ...session,
                      channels: session.channels.filter((x) => x.id !== c.id),
                      routes: session.routes
                        .filter((r) => r.source !== c.id)
                        .map((r) =>
                          r.target === c.id
                            ? {
                                ...r,
                                target: session.channels.find(
                                  (x) => x.kind === "master",
                                )!.id,
                              }
                            : r,
                        ),
                    })
                  }
                >
                  Remover canal
                </button>
              </>
            )}
          </article>
        ))}
      </div>
      <details className="panel routing" open>
        <summary>
          Grafo de roteamento <span>{session.routes.length} conexões</span>
        </summary>
        <p className="muted">
          Cada linha mostra uma aresta do grafo. Saídas principais são
          escolhidas no mixer; sends podem ser adicionados abaixo. Ciclos são
          recusados ao salvar.
        </p>
        <div className="route-graph">
          {session.routes.map((r, i) => (
            <div className="route" key={i}>
              <span className="node">
                {session.channels.find((c) => c.id === r.source)?.name}
              </span>
              <span className="edge">
                {r.kind === "send" ? "send" : "saída"} →
              </span>
              <span className="node">
                {session.channels.find((c) => c.id === r.target)?.name}
              </span>
              {r.kind === "send" && (
                <>
                  <label>
                    Nível dB
                    <input
                      aria-label="Nível do send em dB"
                      type="number"
                      min="-60"
                      max="12"
                      step=".1"
                      value={r.gain_db}
                      onChange={(e) =>
                        onChange({
                          ...session,
                          routes: session.routes.map((x, j) =>
                            i === j ? { ...x, gain_db: +e.target.value } : x,
                          ),
                        })
                      }
                    />
                  </label>
                  <button
                    type="button"
                    aria-label="Remover send"
                    onClick={() =>
                      onChange({
                        ...session,
                        routes: session.routes.filter((_, j) => i !== j),
                      })
                    }
                  >
                    ×
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
        <RoutingGraph session={session} />
        <SendForm session={session} onChange={onChange} />
      </details>
    </>
  );
}

function SendForm({
  session,
  onChange,
}: {
  session: Session;
  onChange: (s: Session) => void;
}) {
  return (
    <div className="send-form">
      <label>
        Origem
        <select id="send-source">
          {session.channels
            .filter((c) => c.kind !== "master")
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
        </select>
      </label>
      <label>
        Destino
        <select id="send-target">
          {session.channels.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={() => {
          const source = (
            document.getElementById("send-source") as HTMLSelectElement
          ).value;
          const target = (
            document.getElementById("send-target") as HTMLSelectElement
          ).value;
          onChange({
            ...session,
            routes: [
              ...session.routes,
              { source, target, kind: "send", gain_db: -12 },
            ],
          });
        }}
        disabled={session.routes.length >= 128}
      >
        ＋ Send
      </button>
    </div>
  );
}

export function Context({
  session: s,
  onChange,
}: {
  session: Session;
  onChange: (s: Session) => void;
}) {
  const set = (patch: Partial<Session>) => onChange({ ...s, ...patch });
  return (
    <div className="panel">
      <span className="eyebrow">01 / CONTEXTO TÉCNICO OBRIGATÓRIO</span>
      <h2>Como essa versão foi feita?</h2>
      <div className="form-grid">
        <label>
          DAW
          <input
            required
            maxLength={80}
            value={s.daw}
            onChange={(e) => set({ daw: e.target.value })}
          />
        </label>
        <label>
          BPM
          <input
            required
            type="number"
            min="30"
            max="300"
            step=".1"
            value={s.bpm}
            onChange={(e) => set({ bpm: +e.target.value })}
          />
        </label>
        <label>
          Etapa
          <select
            value={s.stage}
            onChange={(e) => set({ stage: e.target.value as Session["stage"] })}
          >
            <option value="mix">Mixagem</option>
            <option value="master">Masterização</option>
          </select>
        </label>
        <label>
          Origem do beat
          <select
            value={s.beat_source}
            onChange={(e) =>
              set({ beat_source: e.target.value as Session["beat_source"] })
            }
          >
            <option value="stereo">Beat estéreo</option>
            <option value="multitrack">Multitrack na DAW</option>
          </select>
        </label>
        <label>
          Beat já limitado?
          <select
            value={s.beat_already_limited}
            onChange={(e) =>
              set({
                beat_already_limited: e.target
                  .value as Session["beat_already_limited"],
              })
            }
          >
            <option value="unknown">Não sei</option>
            <option value="yes">Sim</option>
            <option value="no">Não</option>
          </select>
        </label>
        <label>
          Sample rate do export
          <select
            value={s.export_sample_rate}
            onChange={(e) => set({ export_sample_rate: +e.target.value })}
          >
            {[8000, 16000, 22050, 32000, 44100, 48000, 88200, 96000].map(
              (v) => (
                <option key={v} value={v}>
                  {v} Hz
                </option>
              ),
            )}
          </select>
        </label>
        <label>
          Profundidade
          <select
            value={s.export_bit_depth}
            onChange={(e) =>
              set({
                export_bit_depth: e.target.value as Session["export_bit_depth"],
              })
            }
          >
            <option value="16">16 bit PCM</option>
            <option value="24">24 bit PCM</option>
            <option value="32-float">32 bit float</option>
          </select>
        </label>
        <label className="wide">
          Monitoração
          <input
            required
            placeholder="Fone / monitores e ambiente de escuta"
            maxLength={300}
            value={s.listening_setup}
            onChange={(e) => set({ listening_setup: e.target.value })}
          />
        </label>
        <label className="wide">
          Intenção e referências
          <textarea
            required
            placeholder="Ex.: vocal à frente, 808 presente; referência e trecho que quer investigar"
            maxLength={1000}
            value={s.intent}
            onChange={(e) => set({ intent: e.target.value })}
          />
        </label>
      </div>
    </div>
  );
}
