# Ubuntu / CloudPanel — operação pessoal

Alvo: Ubuntu com Python 3.12 e Node 22, 4 vCPU, 8 GB RAM. Exemplos em `deploy/`;
não foram executados em uma VPS real. Não há Docker, Redis, GPU ou dependência paga.

## Instalação

1. Crie usuário de serviço sem login `mixwithme`; clone a branch revisada em
   `/opt/mixwithme`. Código pode ser propriedade de root, legível pelo serviço.
2. Instale Python 3.12/venv, Node 22 e `libsndfile1` por fontes confiáveis.
   Crie `backend/.venv`, instale `requirements.txt`, execute testes.
3. Em `frontend`: `npm ci`, `npm run build`. Crie `.next/cache` e dê escrita
   apenas nessa pasta ao serviço. O build pode usar ~2 GB: faça antes de iniciar
   serviços ou fora da VPS se outros sites estiverem consumindo memória.
4. Crie `/var/lib/mixwithme`, proprietário `mixwithme:mixwithme`, modo 0700.
   Reserve pelo menos 12 GB livres para biblioteca + margem, além do sistema.
5. Crie `/etc/mixwithme.env`, proprietário root, modo 0600:

   ```ini
   API_TOKEN=<gere 32 bytes aleatórios, por exemplo openssl rand -hex 32>
   DATA_DIR=/var/lib/mixwithme
   ```

   A chave não é de uma API paga; é a senha pessoal da aplicação. Guarde-a no
   gerenciador de senhas. Nunca use um exemplo ou a chave da prévia de testes.
6. Copie os três exemplos `.service` para `/etc/systemd/system/`. Ajuste caminho
   do Node caso não seja `/usr/bin/node`. Rode `systemctl daemon-reload` e
   `systemctl enable --now mixwithme-api mixwithme-worker mixwithme-web`.
7. No CloudPanel, configure domínio com TLS e proxy reverso. Integre as locations
   comentadas em `nginx.conf.example` ao vhost HTTPS; as zonas de rate limit vão
   em contexto `http`. Confira com `nginx -t` antes de recarregar. Não exponha
   diretórios do projeto/dados como raiz pública. Não abra portas 3000/8000 no firewall.
8. Faça smoke test HTTPS: acesso inválido recusado, criar sessão, enviar WAV de
   teste, observar queued→running→done, responder e comparar duas versões.

## Limites

| Recurso | Limite |
|---|---|
| WAV | 250 MiB, 1–600 s, 8–96 kHz, mono/estéreo, PCM16/24 ou FLOAT32 |
| Música | 5 WAVs, incluindo trabalhos ativos/falhos |
| Biblioteca | 100 músicas, 40 WAVs totais (~9,77 GiB máximo de áudio) |
| Upload/fila/análise ativos | 3 no total |
| DSP paralelo | 1 subprocesso, timeout 180 s |
| Upload | 120 s, streaming sem multipart em memória |
| JSON | 512 KiB e 15 s, autenticação antes de parsing |
| Reserva de disco | Upload recusado se livre <2 GiB |
| Sessão | 64 canais, 30 plugins/canal, 128 rotas |

SQLite usa WAL, foreign keys, busy timeout e transações IMMEDIATE para reservar
slots antes de aceitar arquivos. O limite de cinco continua válido com uploads
concorrentes. A biblioteca é pequena/pessoal; não há multiusuário, compartilhamento
ou quota por conta. Arquivos inválidos são removidos sem consumir vaga.

systemd limita API a 768 MiB/1 CPU, worker a 1,5 GiB/1,5 CPU, frontend a 1 GiB/1 CPU.
O worker não tem rede; usa um lock de arquivo para impedir dois workers simultâneos.
OPENBLAS/OMP usam uma thread. O serviço mata subprocessos ao parar. Não configure
múltiplos workers Uvicorn: a recuperação de uploads assume um único processo API.

## Segurança

Bearer obrigatório antes de ler corpos, comparado em tempo constante; mínimo
32 caracteres, sem segredo padrão. Autenticação também cobre áudio e OpenAPI.
Somente `/health` é público. TLS e rate limit no proxy são parte da instalação.
Sem CORS aberto, cookies de sessão ou execução de plugins. SQL parametrizado,
IDs gerados no servidor, nomes enviados pelo usuário nunca viram caminhos.
WAVs são inspecionados pelo formato real, não por extensão/MIME. DSP rejeita
NaN/Inf e amplitudes absurdas. Execute sempre sob usuário sem privilégios.

CSP permite scripts inline do Next; não é uma implementação com nonce. Sem HTML
arbitrário no conteúdo do usuário. Dependências devem ser auditadas em atualizações;
não confunda auditoria sem alertas com garantia de ausência de vulnerabilidades.

## Falhas, recuperação e backup

- API reiniciada: uploads interrompidos viram failed; arquivos parciais removidos.
- Worker reiniciado: running volta para queued; relatório substituído atomicamente.
- Timeout/erro de DSP: failed e mensagem visível. Remova a versão e reenvie para tentar.
- Na fila: pode excluir; em upload/análise: aguarde. Exclusão remove WAV, relatório
  e respostas permanentemente; a interface pede confirmação. Não há lixeira.
- `journalctl -u mixwithme-api -u mixwithme-worker -u mixwithme-web` para logs.
  Não registre Authorization. `/health` verifica API, não a vivacidade do worker;
  use `systemctl is-active mixwithme-worker` para supervisioná-lo.
- Para backup consistente simples, pare API e worker, copie **todo** `/var/lib/mixwithme`
  (banco e WAVs), reative. Guarde cópia criptografada fora da VPS. Restore com serviços
  parados, mesmos arquivos e permissões; teste antes de depender do backup.
- Antes de atualizar: backup, testes/build, reinício dos serviços, smoke test.
  Esquema inicial v1 não inclui migração de releases futuras; não faça downgrade
  de um banco alterado sem restaurar backup compatível.

## Próximas entregas

LUFS/true peak com validação, investigação que interprete respostas com evidência,
revisão de contexto por versão na interface, A/B alinhado/loudness matched e testes
de carga na VPS. Nenhuma dessas funções é simulada como se estivesse pronta.
