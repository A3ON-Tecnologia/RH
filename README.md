# Sistema de RH

Aplicativo local de RH (Candidatos, Entrevistas e Contratação) em um único arquivo HTML.
Roda direto no navegador, sem instalação e sem servidor.

## Como usar
Dê **duplo clique em `index.html`**. Funciona no Chrome/Edge, offline.

Telas:
- **Candidatos** — nome, telefone e anexo do PDF do currículo.
- **Entrevistas** — candidato, data, situação, andamento e anexo do formulário.
- **Contratação** — candidato, departamento, admissão e modalidade 45+45 ou 30+30,
  com cálculo automático dos vencimentos dos períodos de experiência.

## Onde os dados ficam
Os registros são gravados no **IndexedDB do navegador**, naquela máquina.
Não são arquivos soltos e **não** vão para o Git automaticamente.

- **Backup** (botão no topo): gera `backup-rh-AAAA-MM-DD.json` com todos os dados,
  incluindo os PDFs (embutidos em base64). É este arquivo que você versiona/leva adiante.
- **Restaurar**: recarrega os dados a partir de um backup `.json`.

## Versionamento no Git
- `index.html`, `schema.sql`, `README.md` → versionar normalmente.
- Dados → só entram no Git se você exportar um **backup `.json`** e commitá-lo.
  (Observação: backups com muitos PDFs podem ficar grandes por causa do base64.)

## Migração futura para MySQL
1. Crie o banco com `schema.sql`.
2. Exporte um **Backup** pelo sistema (`backup-rh-*.json`).
3. Importe o JSON para as tabelas `candidatos`, `entrevistas`, `contratacoes`
   (os nomes dos campos do JSON correspondem às colunas; ver mapeamento abaixo).

### Mapeamento JSON → MySQL
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
