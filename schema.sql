-- ============================================================
--  Sistema de RH — Esquema MySQL
--  Espelha o modelo de dados usado localmente (IndexedDB / backup .json)
--  Uso futuro: criar o banco e importar os dados do backup-rh-*.json
-- ============================================================

CREATE DATABASE IF NOT EXISTS sistema_rh
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sistema_rh;

-- ---------- Candidatos ----------
CREATE TABLE IF NOT EXISTS candidatos (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  nome           VARCHAR(255)  NOT NULL,
  telefone       VARCHAR(30)   NOT NULL,
  curriculo_nome VARCHAR(255)  NULL,           -- nome original do PDF
  curriculo      LONGBLOB      NULL,           -- conteúdo do PDF (ou troque por caminho de arquivo, ver README)
  criado_em      DATE          NULL,
  INDEX idx_cand_nome (nome)
) ENGINE=InnoDB;

-- ---------- Entrevistas ----------
CREATE TABLE IF NOT EXISTS entrevistas (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  cand_id         INT           NOT NULL,
  data            DATE          NOT NULL,
  situacao        VARCHAR(30)   NULL,           -- Agendada / Realizada / Aprovado / Reprovado / Em análise
  andamento       TEXT          NOT NULL,
  formulario_nome VARCHAR(255)  NULL,
  formulario      LONGBLOB      NULL,
  criado_em       DATE          NULL,
  INDEX idx_entr_cand (cand_id),
  CONSTRAINT fk_entr_cand FOREIGN KEY (cand_id)
    REFERENCES candidatos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- Contratações ----------
CREATE TABLE IF NOT EXISTS contratacoes (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  cand_id      INT          NOT NULL,
  departamento VARCHAR(120) NOT NULL,
  admissao     DATE         NOT NULL,
  prazo        INT          NOT NULL,           -- 45 ou 30 (modalidade 45+45 / 30+30)
  fim1         DATE         NOT NULL,           -- fim do 1º período de experiência
  inicio2      DATE         NOT NULL,           -- início da prorrogação (2º período)
  fim_final    DATE         NOT NULL,           -- vencimento final do contrato de experiência
  criado_em    DATE         NULL,
  INDEX idx_contr_cand (cand_id),
  INDEX idx_contr_venc (fim_final),
  CONSTRAINT fk_contr_cand FOREIGN KEY (cand_id)
    REFERENCES candidatos(id) ON DELETE CASCADE
) ENGINE=InnoDB;
