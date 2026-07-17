# Contexto do projeto (handoff para o Claude)

> Documento de continuidade. Ao abrir este projeto no Claude em outra máquina,
> leia este arquivo para retomar o contexto de onde paramos.

## O que é o projeto
Sistema de RH para um escritório de contabilidade (JP Contábil / A3ON Tecnologia).
Feito para acesso de **vários computadores** do escritório ao mesmo tempo.

> **Arquitetura atual: cliente-servidor com MySQL.**
> - `server.py` — back-end em Python: serve a página `index.html` e expõe uma API REST
>   que lê/grava no MySQL (inclusive os PDFs). Roda na máquina onde está o MySQL.
> - `index.html` — front-end; a camada de dados usa `fetch()` para a API (`/api/...`).
> - Os dados ficam **no MySQL** (banco `sistema_rh`), não mais no IndexedDB.
>
> Histórico: a 1ª versão rodava 100% local no navegador (IndexedDB), sem servidor.
> Migrou-se para cliente-servidor para permitir acesso simultâneo de vários PCs.

## Telas implementadas
1. **Candidatos** — nome, telefone (máscara BR) e anexo do PDF do currículo.
2. **Entrevistas** — seleção do candidato, data, situação
   (Agendada/Realizada/Aprovado/Reprovado/Em análise), campo de andamento e anexo do formulário.
3. **Contratação** — candidato, departamento, data de admissão e modalidade
   **45+45** ou **30+30**, com cálculo automático dos vencimentos dos períodos de experiência.
4. **Usuários** — cadastro/exclusão de usuários e troca de senha.

## Login / autenticação
- Tabela `usuarios` (nome único + `senha_hash` PBKDF2, nunca senha em texto puro).
- **Vários usuários**; qualquer usuário logado pode cadastrar outros (sem papel de admin).
- **Primeiro acesso:** se a tabela `usuarios` estiver vazia, a tela mostra "crie o usuário
  administrador" e o `POST /api/usuarios` é liberado só nessa situação (depois exige login).
- Sessão por **cookie HttpOnly** (`rh_sessao`), guardada em memória no servidor (`SESSOES`),
  dura 12h e renova a cada uso. Reiniciar o servidor derruba as sessões (todos relogam).
- Todas as rotas `/api/...` de dados exigem login (401 se não autenticado). Rotas públicas:
  `GET /api/setup`, `POST /api/login`, `POST /api/logout`, e `POST /api/usuarios` só no 1º acesso.
- **Limitação conhecida:** roda em HTTP na LAN, então a senha trafega sem criptografia.
  Aceitável para rede interna; para expor fora, seria preciso HTTPS.

## Regra: quem pode ser contratado
A lista de candidatos da tela de **Contratação** mostra **somente quem tem ao menos uma entrevista
com situação `Aprovado`** (função `carregarSelectCandidatos` com `{somenteAprovados:true}`).
- Se ninguém estiver aprovado, o select exibe "Nenhum candidato aprovado em entrevista".
- Ao **editar** uma contratação existente, o candidato vinculado continua na lista mesmo que a
  situação dele tenha mudado depois (parâmetro `incluirId`) — senão a edição perderia o vínculo.
- A tela de **Entrevistas** continua listando **todos** os candidatos (sem filtro).

## Regra de cálculo da experiência (importante)
Contagem **inclusiva**: o dia da admissão conta como 1º dia do prazo.
- Ex. admissão 16/07/2026, 45+45 → 1º período 16/07→29/08, prorrogação 30/08→13/10 (90 dias).
- Ex. admissão 16/07/2026, 30+30 → 1º período 16/07→14/08, prorrogação 15/08→13/09 (60 dias).
Se o escritório usar outra convenção de contagem, ajustar em `index.html` (função `calcularVencimentos`).

## Onde ficam os dados
No **MySQL** (banco `sistema_rh`) da máquina que roda o `server.py`. Os PDFs ficam
em colunas `LONGBLOB` (com `*_mime` e `*_nome` auxiliares). Botões **Backup**/**Restaurar**
exportam/importam tudo (inclusive PDFs) num `backup-rh-*.json` — mesmo formato da versão antiga,
então um backup do IndexedDB pode ser restaurado direto no MySQL pela tela.

## Arquivos do repositório
- `index.html` — front-end (HTML/CSS/JS); camada de dados chama a API via `fetch`.
- `server.py` — back-end Python (http.server + PyMySQL). Serve a página e a API REST.
- `config.json` — conexão do banco e porta. **Contém a senha → fora do Git** (ver `.gitignore`).
- `config.example.json` — modelo do `config.json` (versionado).
- `iniciar-servidor.bat` — atalho para ligar o servidor manualmente (dois cliques).
- `instalar-servico.bat` + `instalar-servico.ps1` — registram o servidor para iniciar no boot
  (Agendador de Tarefas, tarefa **"RH"**, conta SYSTEM, gatilho AtStartup, reinicia 3x se falhar).
  Rodar como administrador. `reiniciar-servico.bat` / `desinstalar-servico.bat` gerenciam a tarefa.
- `servidor.log` — log gerado quando roda como serviço (`server.py --log`). Fora do Git.
- `schema.sql` — cria banco + tabelas (candidatos, entrevistas, contratacoes) + usuário opcional.
- `README.md` — instruções de instalação/uso. `CONTEXTO.md` — este handoff.

## Como rodar (resumo)
1. `pip install PyMySQL` (feito nesta máquina).
2. Criar o banco: rodar `schema.sql` no MySQL (feito).
3. Preencher a **senha** do MySQL em `config.json` (feito).
4. `instalar-servico.bat` como administrador (sobe no boot) — ou `iniciar-servidor.bat` para abrir manualmente.
5. Acessar `http://localhost:8689` (nesta máquina) ou `http://IP-DA-MAQUINA:8689` (nos outros PCs).

## Ambiente desta instalação (jul/2026)
- Windows Server 2022; Python em `C:\Python314\python.exe`; serviço do banco: **MySQL80**.
- **Porta 8689** — a 8080 já está ocupada pelo **Apache (`httpd`)** nesta máquina.
- IP da máquina servidor na rede: `192.168.0.214`.
- No boot o MySQL pode demorar a subir: `server.py` tenta conectar 30x (5s) antes de desistir.
- **Armadilha:** o serviço roda como **SYSTEM**, que NÃO enxerga pacotes instalados no perfil do
  usuário (`C:\Users\...\AppData\Roaming\Python\...`). O PyMySQL precisa estar na pasta geral
  (`C:\Python314\Lib\site-packages`) — um `pip install` sem admin cai no perfil e o serviço falha
  com "Driver do MySQL nao encontrado". O `instalar-servico.ps1` já garante isso automaticamente.

## Dependências / requisitos
- Python 3 + pacote **PyMySQL** na máquina servidor.
- MySQL rodando com o banco `sistema_rh`.
- Para acesso de outros PCs: liberar a **porta 8689** no Firewall do Windows da máquina servidor.

## Próximos passos / pendências
- [ ] Rodar `instalar-servico.bat` como administrador e conferir que sobe após um reboot.
- [ ] Liberar a porta 8689 no Firewall do Windows (para os outros computadores acessarem).
- [ ] Commit/push destas mudanças (migração p/ MySQL + serviço) — ainda não enviado ao GitHub.
- [ ] (Opcional) Mover o projeto para um caminho estável (ex.: `C:\SistemaRH`) em vez de
      `C:\Users\cassio\.claude\projects\...`, que é pasta de trabalho do Claude Code.
- [ ] (Opcional) Criar usuário `rh_app` no MySQL em vez de usar `root` (seção comentada no `schema.sql`).
- [ ] (Opcional) Alternativa aos BLOBs: salvar PDFs em pasta e guardar só o caminho.

## Endpoints da API (referência rápida)
- `GET  /`                       → serve a página `index.html`
- `GET  /api/setup`              → {precisaSetup} — se ainda não há nenhum usuário (público)
- `POST /api/login`              → {usuario,senha} → seta cookie de sessão (público)
- `POST /api/logout`             → encerra a sessão
- `GET  /api/me`                 → usuário logado (ou 401)
- `GET  /api/usuarios`           → lista usuários | `POST` cria | `PUT /{id}` troca senha | `DELETE /{id}`
- `GET  /api/{store}`            → lista (anexos vêm como flag true/false)
- `GET  /api/{store}/{id}`       → registro completo (anexos em base64 data URL)
- `POST /api/{store}`            → cria (retorna `{id}`)
- `PUT  /api/{store}/{id}`       → atualiza (só os campos enviados; anexo só se enviado)
- `DELETE /api/{store}/{id}`     → exclui
- `GET  /api/backup`             → JSON com tudo (formato `backup-rh-*.json`)
- `POST /api/restore`            → substitui todos os dados pelo JSON enviado
  (`{store}` = candidatos | entrevistas | contratacoes)

## Estado do Git
- Remote: `https://github.com/A3ON-Tecnologia/RH.git` (branch `main`).
- Projeto já enviado (push feito). Para atualizar: `git add . && git commit -m "..." && git push`.
- **Não** commitar `config.json` (tem senha; já está no `.gitignore`).
