-- ============================================================
--  Sistema de RH — Script de instalação do banco (MySQL / MariaDB)
--  Cria o banco, as tabelas e (opcionalmente) o usuário da aplicação.
--  Espelha o modelo de dados usado localmente (IndexedDB / backup .json)
--
--  Como rodar no servidor:
--    mysql -u root -p < schema.sql
--  (ou cole o conteudo no MySQL Workbench / phpMyAdmin e execute)
-- ============================================================

-- ---------- 1) Banco de dados ----------
CREATE DATABASE IF NOT EXISTS sistema_rh
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sistema_rh;

-- ---------- 2) Candidatos ----------
CREATE TABLE IF NOT EXISTS candidatos (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  nome           VARCHAR(255)  NOT NULL,
  telefone       VARCHAR(30)   NOT NULL,
  curriculo_nome VARCHAR(255)  NULL,           -- nome original do PDF
  curriculo      LONGBLOB      NULL,           -- conteúdo do PDF (ou troque por caminho de arquivo, ver README)
  curriculo_mime VARCHAR(120)  NULL,           -- tipo do arquivo (ex.: application/pdf)
  criado_em      DATE          NULL,
  INDEX idx_cand_nome (nome)
) ENGINE=InnoDB;

-- ---------- 3) Entrevistas ----------
CREATE TABLE IF NOT EXISTS entrevistas (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  cand_id         INT           NOT NULL,
  data            DATE          NOT NULL,
  situacao        VARCHAR(30)   NULL,           -- Agendada / Realizada / Aprovado / Reprovado / Em análise
  andamento       TEXT          NOT NULL,
  formulario_nome VARCHAR(255)  NULL,
  formulario      LONGBLOB      NULL,
  formulario_mime VARCHAR(120)  NULL,           -- tipo do arquivo anexado
  criado_em       DATE          NULL,
  INDEX idx_entr_cand (cand_id),
  CONSTRAINT fk_entr_cand FOREIGN KEY (cand_id)
    REFERENCES candidatos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- 4) Contratações ----------
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

-- ---------- 5) Usuários (login do sistema) ----------
-- A senha é guardada com hash PBKDF2 (nunca em texto puro). O primeiro
-- usuário é criado pela própria tela, no "primeiro acesso".
CREATE TABLE IF NOT EXISTS usuarios (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  nome       VARCHAR(80)  NOT NULL UNIQUE,        -- nome de login
  senha_hash VARCHAR(255) NOT NULL,               -- pbkdf2$iters$salt$hash
  criado_em  DATE         NULL
) ENGINE=InnoDB;

-- ============================================================
--  5) Usuário da aplicação (OPCIONAL, porém recomendado)
--  Evita usar o 'root' na aplicação. TROQUE a senha abaixo antes de rodar!
--  Descomente as 3 linhas se quiser criar o usuário agora.
-- ============================================================
-- CREATE USER IF NOT EXISTS 'rh_app'@'%' IDENTIFIED BY 'TROQUE_ESTA_SENHA';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON sistema_rh.* TO 'rh_app'@'%';
-- FLUSH PRIVILEGES;

-- ============================================================
--  6) Verificação — confirma que tudo foi criado
-- ============================================================
SELECT 'Banco e tabelas criados com sucesso.' AS status;
SHOW TABLES;
