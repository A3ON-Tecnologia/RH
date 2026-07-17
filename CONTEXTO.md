# Contexto do projeto (handoff para o Claude)

> Documento de continuidade. Ao abrir este projeto no Claude em outra máquina,
> leia este arquivo para retomar o contexto de onde paramos.

## O que é o projeto
Sistema de RH local, em **um único arquivo HTML** (`index.html`), que roda no
navegador sem instalação e sem servidor. Feito para um escritório de contabilidade
(JP Contábil / A3ON Tecnologia).

## Telas implementadas
1. **Candidatos** — nome, telefone (máscara BR) e anexo do PDF do currículo.
2. **Entrevistas** — seleção do candidato, data, situação
   (Agendada/Realizada/Aprovado/Reprovado/Em análise), campo de andamento e anexo do formulário.
3. **Contratação** — candidato, departamento, data de admissão e modalidade
   **45+45** ou **30+30**, com cálculo automático dos vencimentos dos períodos de experiência.

## Regra de cálculo da experiência (importante)
Contagem **inclusiva**: o dia da admissão conta como 1º dia do prazo.
- Ex. admissão 16/07/2026, 45+45 → 1º período 16/07→29/08, prorrogação 30/08→13/10 (90 dias).
- Ex. admissão 16/07/2026, 30+30 → 1º período 16/07→14/08, prorrogação 15/08→13/09 (60 dias).
Se o escritório usar outra convenção de contagem, ajustar em `index.html` (função `calcularVencimentos`).

## Onde ficam os dados
No **IndexedDB do navegador** da máquina onde o `index.html` é aberto.
Não são arquivos e **não** vão para o Git. Botões **Backup**/**Restaurar** exportam/importam
tudo (inclusive PDFs) num `backup-rh-*.json`.

## Arquivos do repositório
- `index.html` — o sistema completo (HTML/CSS/JS, IndexedDB).
- `schema.sql` — esquema MySQL espelhando o modelo (candidatos, entrevistas, contratacoes).
- `README.md` — instruções de uso, Git e migração.
- `CONTEXTO.md` — este handoff.

## Decisões tomadas
- Rodar **local** por enquanto; versionar no Git (repo privado `A3ON-Tecnologia/RH`).
- **Futuro:** subir num servidor que já tem **MySQL** e migrar os dados do backup para o banco.
- PDFs no MySQL: decidir entre `LONGBLOB` (arquivo no banco) ou salvar em pasta e guardar só o caminho.

## Próximos passos / pendências
- [ ] No servidor do banco: rodar `schema.sql` para criar as tabelas.
- [ ] Escrever o **script de importação** que lê `backup-rh-*.json` e insere no MySQL
      (linguagem a definir — PHP ou Python). **Ainda não foi feito.**
- [ ] Definir armazenamento dos PDFs (BLOB vs. caminho em pasta).
- [ ] (Opcional) Evoluir para arquitetura cliente-servidor se vários computadores
      precisarem acessar os mesmos dados simultaneamente.

## Estado do Git
- Remote: `https://github.com/A3ON-Tecnologia/RH.git` (branch `main`).
- Projeto já enviado (push feito). Para atualizar: `git add . && git commit -m "..." && git push`.
