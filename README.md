# Sistema de RH

Sistema de RH (Candidatos, Entrevistas e Contratação) com back-end em Python e banco **MySQL**.
Vários computadores do escritório acessam os mesmos dados pela rede, por um navegador.

## Requisitos (na máquina servidor)
- **MySQL** rodando, com o banco `sistema_rh` criado (rode `schema.sql`).
- **Python 3** com o pacote **PyMySQL**: `python -m pip install PyMySQL`.

## Instalação (uma vez)
1. **Criar o banco:** no MySQL, execute o `schema.sql` (cria banco + tabelas).
   - Linha de comando: `mysql -u root -p < schema.sql`
   - Ou pelo MySQL Workbench: abra o arquivo e execute (⚡).
2. **Configurar a senha:** copie `config.example.json` para `config.json` e preencha o campo
   `password` com a senha do seu MySQL (a mesma que você usa no Workbench).
3. **Firewall (para acesso de outros PCs):** libere a porta **8689** no Firewall do Windows
   da máquina servidor (PowerShell como administrador):
   ```
   netsh advfirewall firewall add rule name="Sistema RH 8689" dir=in action=allow protocol=TCP localport=8689
   ```

> A porta padrão é **8689** (definida em `config.json`). A 8080 costuma estar ocupada pelo Apache.

## Como usar

### Opção A — iniciar junto com o Windows (recomendado)
Clique com o **botão direito** em **`instalar-servico.bat`** → **Executar como administrador**.
Pronto: o servidor passa a subir sozinho no boot, sem janela e sem precisar de login.

- `reiniciar-servico.bat` — reinicie após alterar o `config.json` (também como administrador).
- `desinstalar-servico.bat` — remove a inicialização automática.
- `servidor.log` — o que aconteceu (útil se algo não subir).

### Opção B — abrir manualmente
Dê **dois cliques em `iniciar-servidor.bat`** (ou rode `python server.py`) e deixe a janela aberta.

### Acessar
- **Nesta máquina:** `http://localhost:8689`
- **Nos outros computadores:** `http://IP-DA-MAQUINA-SERVIDOR:8689`
  (o `iniciar-servidor.bat` mostra o IP certo na tela ao ligar).

### Login
O sistema é protegido por **usuário e senha**. No **primeiro acesso** (banco sem usuários),
a tela pede para criar o primeiro usuário — ele já entra automaticamente. Depois, cada pessoa
entra com o seu login. Qualquer usuário logado pode cadastrar novos usuários na aba **Usuários**.

> As senhas são guardadas com hash (não em texto puro). Como o sistema roda em HTTP na rede
> interna, use-o apenas na LAN do escritório.

Telas:
- **Candidatos** — nome, telefone e anexo do PDF do currículo.
- **Entrevistas** — candidato, data, situação, andamento e anexo do formulário.
- **Contratação** — candidato, departamento, admissão e modalidade 45+45 ou 30+30,
  com cálculo automático dos vencimentos dos períodos de experiência.
  > Só aparecem aqui os candidatos com **entrevista aprovada**. Se a lista estiver vazia,
  > registre antes a entrevista com situação **Aprovado** na tela de Entrevistas.
- **Usuários** — cadastrar/excluir usuários e trocar senha.

## Onde os dados ficam
No **MySQL** (banco `sistema_rh`) da máquina servidor. Os PDFs ficam em colunas `LONGBLOB`.

- **Backup** (botão no topo): gera `backup-rh-AAAA-MM-DD.json` com todos os dados,
  incluindo os PDFs (embutidos em base64).
- **Restaurar**: substitui os dados atuais pelos de um backup `.json`
  (compatível com backups da versão antiga que usava IndexedDB).

## Versionamento no Git
- `index.html`, `server.py`, `schema.sql`, `config.example.json`, `README.md` → versionar normalmente.
- **`config.json` NÃO** (contém a senha do banco; já está no `.gitignore`).
- Dados → só entram no Git se você exportar um **backup `.json`** e commitá-lo.
  (Observação: backups com muitos PDFs podem ficar grandes por causa do base64.)

## Restaurar dados da versão antiga (IndexedDB → MySQL)
Se você tem um `backup-rh-*.json` da versão local antiga, use o botão **Restaurar**
na tela do sistema já rodando no MySQL — o servidor decodifica os PDFs e grava tudo
nas tabelas automaticamente. Não é preciso importar manualmente.

### Mapeamento JSON → MySQL (referência)
| JSON (backup)        | Tabela.coluna              | Observação                                  |
|----------------------|----------------------------|---------------------------------------------|
| candidato.nome       | candidatos.nome            |                                             |
| candidato.telefone   | candidatos.telefone        |                                             |
| candidato.curriculoNome | candidatos.curriculo_nome |                                          |
| candidato.curriculo  | candidatos.curriculo       | data URL base64 → decodificar para o BLOB   |
| entrevista.candId    | entrevistas.cand_id        | FK para candidatos.id                       |
| entrevista.data      | entrevistas.data           |                                             |
| entrevista.situacao  | entrevistas.situacao       |                                             |
| entrevista.andamento | entrevistas.andamento      |                                             |
| entrevista.formulario| entrevistas.formulario     | data URL base64 → decodificar para o BLOB   |
| contratacao.candId   | contratacoes.cand_id       | FK                                          |
| contratacao.departamento | contratacoes.departamento |                                        |
| contratacao.admissao | contratacoes.admissao      |                                             |
| contratacao.prazo    | contratacoes.prazo         | 45 ou 30                                    |
| contratacao.fim1 / inicio2 / fimFinal | contratacoes.fim1 / inicio2 / fim_final | datas de vencimento |

> Alternativa aos BLOBs: em vez de guardar o PDF no banco, salvar os arquivos em uma
> pasta e gravar apenas o **caminho** (troque `LONGBLOB` por `VARCHAR(500)` no `schema.sql`).

## Regra de cálculo da experiência
Contagem **inclusiva**: o dia da admissão conta como 1º dia do prazo.
Ex.: admissão 16/07 na modalidade 45+45 → 1º período vence 29/08, prorrogação 30/08 a 13/10 (90 dias).
