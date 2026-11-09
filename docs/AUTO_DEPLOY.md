# Atualização automática do checkout na VPS

Workflow: `.github/workflows/deploy.yml`. Após push/merge na `main`, testa as
proteções e atualiza o checkout remoto por SSH. PRs executam apenas os testes,
sem secrets ou conexão à VPS. Disparo manual aceita `check_only` (padrão: true).

**Escopo: atualização do código por Git.** Não instala dependências, não faz build,
não reinicia serviços, não migra banco e não configura CloudPanel. Essas etapas
precisam de uma entrega de deploy da aplicação separada. O PR do protótipo permanece
independente; este workflow não o incorpora automaticamente.

## Configuração

- Repositório: `antonioacodes/mixwithme`.
- Pasta absoluta do checkout: secret `VPS_PROJECT_PATH`, nunca publicada no código.
- Secrets já cadastrados: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT`.
- `VPS_USER` deve ser o usuário não-root `deploy`.
- Identidade pública Ed25519 da VPS: secret `VPS_KNOWN_HOSTS`, no formato
  `mixwithme-vps ssh-ed25519 <chave pública verificada>`, usando alias independente
  do endereço secreto. Valide a identidade fora do workflow. Não usamos
  `ssh-keyscan` como fonte de confiança no workflow.

## Pré-requisitos na VPS

Ubuntu/Linux, Python >=3.9, Git, SSH, usuário deploy com acesso ao GitHub (se privado),
permissão de travessia nos diretórios ancestrais e escrita no checkout e `.git`.
O checkout deve existir, estar em `main`, ter origin correto e não conter modificações
locais, arquivos não rastreados ou commits divergentes. O script não clona, não troca
branch, não faz `reset --hard`, não limpa, não faz stash e não força atualização.

Não altere recursivamente o proprietário do site CloudPanel sem revisar sua configuração.
Um administrador deve conceder somente as permissões necessárias ao usuário deploy.
Se Git detectar ownership diferente, configure `safe.directory` **somente para esta
pasta**, depois de confirmar proprietário/origin; nunca use `safe.directory '*'`.

## Proteções

- A chave privada fica em diretório temporário 0700/arquivo 0600 e é removida no fim.
- Sem senha interativa, agent forwarding ou desativação da verificação da chave do servidor.
- `contents: read`, secrets somente no job de SSH; checkout sem persistir credenciais.
- Uma execução por vez no GitHub e lock local no checkout.
- Compara origin, usuário, pasta raiz e branch; checa permissões antes da atualização.
- Recusa arquivos alterados/não rastreados, flags que escondem alterações e operações Git incompletas.
- Faz fetch de main e verifica o SHA exato do evento. Execução obsoleta é ignorada,
  sem retornar a versão anterior. Exige fast-forward; recusa commits locais divergentes.
- Protege inclusive arquivos ignorados (`.env` etc.) contra colisões com arquivos recebidos.
- Após merge, verifica SHA e estado limpo. Falhas não disparam recuperação destrutiva.

Evite editar o checkout manualmente durante deploy: o lock coordena este script,
mas não obriga editores/Git externos a respeitá-lo. Isto não é um sistema de releases
atômicos nem garante rollback após falha de disco. Mantenha backup dos dados.

## Teste

```sh
bash -n scripts/deploy-ssh.sh
python3 -m unittest discover -s tests -p 'test_deploy.py' -v
```

Os testes usam repositórios Git temporários, sem rede ou secrets. Em Actions,
`Run workflow` na main com `check_only=true` verifica conexão e permissões sem mudar
arquivos da aplicação (ainda grava lock e atualiza metadados com fetch).
`check_only=false` ou push em main faz a atualização. O workflow manual precisa
estar na branch padrão para aparecer no GitHub.

Se a VPS for reinstalada e mudar sua chave SSH, valide a nova identidade fora do
workflow antes de atualizar `VPS_KNOWN_HOSTS`; não desative StrictHostKeyChecking.
