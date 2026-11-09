# MixWithMe

Laboratório pessoal de mix/master TRAP: Next.js + FastAPI/Python DSP + SQLite.
O WAV é medido localmente na CPU. A sessão ajuda a formular perguntas; não permite
reconstruir o áudio dos canais nem confirmar causas perceptivas.

## Implementado

- Músicas com contexto técnico obrigatório e até **cinco versões WAV** por música.
- Snapshot imutável de contexto, mixer, roteamento e plugins por upload.
- Até 64 canais/buses/retornos, fader/pan/largura declarados, saídas, sends e grafo.
- Plugins ordenáveis com função e bypass, **sem parâmetros no cadastro**.
- Fila SQLite persistente, um worker CPU e timeout por análise.
- Medições transparentes, triagem em cinco dimensões, hipóteses com evidências,
  perguntas e respostas por versão. “Não sei” é válido.
- Reprodução autenticada do WAV original e comparação numérica A/B.
- Interface em português, acesso pessoal, limites de recursos, testes e CI.

## Limites explícitos

Sem stems, correção automática, GPU, serviços pagos, LLM ou chat livre. Perguntas
são regras determinísticas. Respostas registram contexto humano e não confirmam
diagnósticos automaticamente. Não alteram os números medidos.

**LUFS e true peak ainda não são calculados.** RMS não é loudness percebido;
sample peak não é true peak. A/B não alinha nem normaliza os arquivos. Frequências,
clareza e transientes mostram nota indisponível, com motivo. Dinâmica/estéreo têm
triagens 50/100, nunca uma nota geral de qualidade. Silêncio não recebe nota positiva.

Leia [os métodos](docs/MEASUREMENTS.md) e [a operação Ubuntu/CloudPanel](docs/DEPLOYMENT.md).

## Rodar localmente

Requisitos: **Python 3.12**, **Node.js 22**, macOS/Linux. Ubuntu: `python3.12-venv libsndfile1`.
Dependências travadas em `backend/requirements.txt` e `frontend/package-lock.json`.

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
export API_TOKEN="$(openssl rand -hex 32)"
export DATA_DIR="$(pwd)/data"
# Guarde a chave em seu gerenciador de senhas e use-a na interface.
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Outro terminal, com o mesmo `DATA_DIR` absoluto:

```sh
cd backend
export DATA_DIR="$(pwd)/data"
.venv/bin/python -m app.worker
```

```sh
cd frontend
npm ci
npm run build
npm start
```

Abra `http://127.0.0.1:3000`. Chave apenas na memória da aba, sem localStorage,
cookies ou URL. Recarregar bloqueia a sessão. Produção exige HTTPS e os limites de
proxy do guia. O rewrite `/api` do Next serve ao desenvolvimento; Nginx encaminha
uploads direto à API em produção.

Fluxo: desbloquear → criar música/contexto → configurar mixer/plugins → salvar →
enviar WAV → aguardar → investigar → enviar outra versão → comparar.
WAV PCM16/PCM24/FLOAT32, mono/estéreo, 8–96 kHz, 1–600 s e até 250 MiB.

## Verificar

```sh
cd backend
.venv/bin/python -m pytest -q
cd ../frontend
npm run build
npm run typecheck
npm audit --omit=dev --audit-level=high
```

Testes cobrem seno calibrado, silêncio, mono, DC, contrafase, valores não finitos,
cauda de uma amostra, autenticação, contexto, ciclos, fila, cinco versões sob
concorrência, uploads, snapshots, respostas, comparação e exclusão.

## Estrutura

`frontend/app`: interface; `backend/app`: API/DSP/worker; `backend/tests`: testes;
`deploy`: systemd/Nginx; `docs`: métodos/operação. Esquema SQLite inicial v1 é
criado idempotentemente. Alterações futuras exigem migrações explícitas e backup.
Nunca versione WAVs, bancos, chaves ou arquivos de ambiente.
