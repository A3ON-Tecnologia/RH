# -*- coding: utf-8 -*-
# ============================================================
#  Sistema de RH — Back-end (Python + MySQL)
#  Serve a pagina index.html e expoe uma API que le/grava no MySQL.
#  Rodar:  python server.py   (ou dois cliques em iniciar-servidor.bat)
# ============================================================
import json, base64, os, sys, socket, datetime, time, hashlib, hmac, secrets, http.cookies, decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Modo servico (--log): roda sem janela; tudo vai para servidor.log
MODO_SERVICO = "--log" in sys.argv
if MODO_SERVICO:
    sys.stdout = sys.stderr = open(os.path.join(BASE_DIR, "servidor.log"),
                                   "a", encoding="utf-8", buffering=1)

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    print("Driver do MySQL nao encontrado. Rode:  python -m pip install PyMySQL")
    sys.exit(1)

# ---------- Configuracao ----------
with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
    CONFIG = json.load(f)
DB = CONFIG["mysql"]
SRV = CONFIG["server"]

# ---------- Metadados das tabelas ----------
# Cada file = (chaveJsonDados, colunaBlob, colunaNome, colunaMime, chaveJsonNome)
STORES = {
    "candidatos": {
        "scalars": [("nome", "nome"), ("telefone", "telefone"), ("criadoEm", "criado_em")],
        "files": [("curriculo", "curriculo", "curriculo_nome", "curriculo_mime", "curriculoNome")],
    },
    "entrevistas": {
        "scalars": [("candId", "cand_id"), ("data", "data"), ("hora", "hora"), ("situacao", "situacao"),
                     ("idade", "idade"), ("estadoCivil", "estado_civil"), ("mora", "mora"),
                     ("faculdade", "faculdade"), ("faseFaculdade", "fase_faculdade"),
                     ("trocaFaculdade", "troca_faculdade"), ("pretensaoSalarial", "pretensao_salarial"),
                     ("andamento", "andamento"), ("criadoEm", "criado_em")],
        "files": [("formulario", "formulario", "formulario_nome", "formulario_mime", "formularioNome")],
    },
    "contratacoes": {
        "scalars": [("candId", "cand_id"), ("departamento", "departamento"), ("admissao", "admissao"),
                     ("prazo", "prazo"), ("fim1", "fim1"), ("inicio2", "inicio2"),
                     ("fimFinal", "fim_final"), ("criadoEm", "criado_em")],
        "files": [],
    },
}
ORDEM_TABELAS = ["candidatos", "entrevistas", "contratacoes"]
DATE_COLS = {"data", "admissao", "fim1", "inicio2", "fim_final", "criado_em"}
INT_COLS = {"cand_id", "prazo", "idade"}

# ---------- Login / sessões ----------
SESSAO_HORAS = 12                 # quanto tempo o login dura sem atividade
SESSOES = {}                      # token -> {"uid":int, "usuario":str, "expira":float}
PBKDF2_ITERS = 200000


def hash_senha(senha, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERS)
    return f"pbkdf2${PBKDF2_ITERS}${salt}${dk.hex()}"


def verificar_senha(senha, armazenado):
    try:
        _alg, iters, salt, h = armazenado.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), h)
    except Exception:
        return False


def criar_sessao(uid, nome):
    token = secrets.token_urlsafe(32)
    SESSOES[token] = {"uid": uid, "usuario": nome, "expira": time.time() + SESSAO_HORAS * 3600}
    return token


def sessao_valida(token):
    s = SESSOES.get(token)
    if not s:
        return None
    if s["expira"] < time.time():
        SESSOES.pop(token, None)
        return None
    s["expira"] = time.time() + SESSAO_HORAS * 3600   # renova a cada uso
    return s


# ---------- Banco ----------
def conectar(autocommit=True):
    return pymysql.connect(
        host=DB["host"], port=int(DB.get("port", 3306)),
        user=DB["user"], password=DB.get("password", ""), database=DB["database"],
        charset="utf8mb4", autocommit=autocommit, cursorclass=pymysql.cursors.DictCursor,
    )


def add_col_if_missing(cur, table, col, ddl):
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
        (DB["database"], table, col),
    )
    if cur.fetchone()["n"] == 0:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        print(f"  [migracao] coluna {table}.{col} criada")


def ensure_min_varchar(cur, table, col, minlen):
    """Alarga uma coluna VARCHAR se ela estiver menor que o necessario."""
    cur.execute(
        "SELECT character_maximum_length AS n FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
        (DB["database"], table, col),
    )
    row = cur.fetchone()
    if row and row["n"] is not None and row["n"] < minlen:
        cur.execute(f"ALTER TABLE {table} MODIFY {col} VARCHAR({minlen}) NULL")
        print(f"  [migracao] coluna {table}.{col} ampliada para VARCHAR({minlen})")


def ensure_schema():
    """Garante as colunas de mime (anexos) e a tabela de usuarios."""
    conn = conectar()
    try:
        cur = conn.cursor()
        add_col_if_missing(cur, "candidatos", "curriculo_mime", "VARCHAR(120) NULL")
        add_col_if_missing(cur, "entrevistas", "formulario_mime", "VARCHAR(120) NULL")
        add_col_if_missing(cur, "entrevistas", "hora", "VARCHAR(5) NULL")
        add_col_if_missing(cur, "entrevistas", "idade", "TINYINT UNSIGNED NULL")
        add_col_if_missing(cur, "entrevistas", "estado_civil", "VARCHAR(20) NULL")
        add_col_if_missing(cur, "entrevistas", "mora", "VARCHAR(20) NULL")
        add_col_if_missing(cur, "entrevistas", "faculdade", "VARCHAR(255) NULL")
        add_col_if_missing(cur, "entrevistas", "fase_faculdade", "VARCHAR(255) NULL")
        add_col_if_missing(cur, "entrevistas", "troca_faculdade", "VARCHAR(10) NULL")
        ensure_min_varchar(cur, "entrevistas", "troca_faculdade", 10)
        add_col_if_missing(cur, "entrevistas", "pretensao_salarial", "DECIMAL(10,2) NULL")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS usuarios ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  nome VARCHAR(80) NOT NULL UNIQUE,"
            "  senha_hash VARCHAR(255) NOT NULL,"
            "  criado_em DATE NULL"
            ") ENGINE=InnoDB"
        )
    finally:
        conn.close()


# ---------- Usuários ----------
def contar_usuarios():
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM usuarios")
        return cur.fetchone()["n"]
    finally:
        conn.close()


def buscar_usuario(nome):
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE nome=%s", (nome,))
        return cur.fetchone()
    finally:
        conn.close()


def listar_usuarios():
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nome, criado_em FROM usuarios ORDER BY nome")
        return [{"id": r["id"], "nome": r["nome"], "criadoEm": to_json_value(r["criado_em"])}
                for r in cur.fetchall()]
    finally:
        conn.close()


def criar_usuario(nome, senha):
    nome = (nome or "").strip()
    if not nome or not senha:
        raise ValueError("Informe usuario e senha.")
    if len(senha) < 4:
        raise ValueError("A senha deve ter ao menos 4 caracteres.")
    if buscar_usuario(nome):
        raise ValueError("Ja existe um usuario com esse nome.")
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO usuarios (nome, senha_hash, criado_em) VALUES (%s, %s, CURDATE())",
                    (nome, hash_senha(senha)))
        return cur.lastrowid
    finally:
        conn.close()


def alterar_senha(uid, senha):
    if not senha or len(senha) < 4:
        raise ValueError("A senha deve ter ao menos 4 caracteres.")
    conn = conectar()
    try:
        conn.cursor().execute("UPDATE usuarios SET senha_hash=%s WHERE id=%s", (hash_senha(senha), int(uid)))
    finally:
        conn.close()


def excluir_usuario(uid):
    if contar_usuarios() <= 1:
        raise ValueError("Nao e possivel excluir o unico usuario do sistema.")
    conn = conectar()
    try:
        conn.cursor().execute("DELETE FROM usuarios WHERE id=%s", (int(uid),))
    finally:
        conn.close()


# ---------- Conversoes ----------
def to_json_value(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()[:10] if isinstance(v, datetime.date) and not isinstance(v, datetime.datetime) else v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def coerce(col, val):
    if val == "":
        return None
    if col in DATE_COLS:
        return val
    if col in INT_COLS:
        return int(val) if val not in (None, "") else None
    return val


def parse_data_url(s):
    """'data:mime;base64,XXXX' -> (mime, bytes)"""
    cabecalho, dados = s.split(",", 1)
    mime = cabecalho[5:].split(";")[0] or "application/octet-stream"
    return mime, base64.b64decode(dados)


def row_to_summary(store, row):
    meta = STORES[store]
    out = {"id": row["id"]}
    for jkey, col in meta["scalars"]:
        out[jkey] = to_json_value(row.get(col))
    for (jdata, blobcol, namecol, mimecol, jname) in meta["files"]:
        out[jname] = row.get(namecol)
        out[jdata] = bool(row.get(blobcol + "_has"))
    return out


def row_to_detail(store, row):
    meta = STORES[store]
    out = {"id": row["id"]}
    for jkey, col in meta["scalars"]:
        out[jkey] = to_json_value(row.get(col))
    for (jdata, blobcol, namecol, mimecol, jname) in meta["files"]:
        out[jname] = row.get(namecol)
        blob = row.get(blobcol)
        if blob is not None:
            mime = row.get(mimecol) or "application/octet-stream"
            b64 = base64.b64encode(blob).decode("ascii")
            out[jdata] = f"data:{mime};base64,{b64}"
    return out


def summary_select(store):
    meta = STORES[store]
    cols = ["id"] + [col for _, col in meta["scalars"]]
    for (jdata, blobcol, namecol, mimecol, jname) in meta["files"]:
        cols.append(namecol)
        cols.append(f"({blobcol} IS NOT NULL) AS {blobcol}_has")
    return ", ".join(cols)


def detail_select(store):
    meta = STORES[store]
    cols = ["id"] + [col for _, col in meta["scalars"]]
    for (jdata, blobcol, namecol, mimecol, jname) in meta["files"]:
        cols += [namecol, mimecol, blobcol]
    return ", ".join(cols)


# ---------- Operacoes ----------
def listar(store):
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {summary_select(store)} FROM {store}")
        return [row_to_summary(store, r) for r in cur.fetchall()]
    finally:
        conn.close()


def obter(store, id):
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {detail_select(store)} FROM {store} WHERE id=%s", (id,))
        row = cur.fetchone()
        return row_to_detail(store, row) if row else None
    finally:
        conn.close()


def _insert(cur, store, data):
    meta = STORES[store]
    cols, vals = [], []
    if data.get("id") is not None:
        cols.append("id"); vals.append(int(data["id"]))
    for jkey, col in meta["scalars"]:
        if jkey in data:
            cols.append(col); vals.append(coerce(col, data[jkey]))
    for (jdata, blobcol, namecol, mimecol, jname) in meta["files"]:
        v = data.get(jdata)
        if isinstance(v, str) and v.startswith("data:"):
            mime, blob = parse_data_url(v)
            cols += [blobcol, mimecol, namecol]
            vals += [blob, mime, data.get(jname)]
    placeholders = ", ".join(["%s"] * len(cols))
    cur.execute(f"INSERT INTO {store} ({', '.join(cols)}) VALUES ({placeholders})", vals)
    return cur.lastrowid


def criar(store, data):
    conn = conectar()
    try:
        cur = conn.cursor()
        return _insert(cur, store, data)
    finally:
        conn.close()


def atualizar(store, id, data):
    meta = STORES[store]
    sets, vals = [], []
    for jkey, col in meta["scalars"]:
        if jkey in data:
            sets.append(f"{col}=%s"); vals.append(coerce(col, data[jkey]))
    for (jdata, blobcol, namecol, mimecol, jname) in meta["files"]:
        v = data.get(jdata)
        if isinstance(v, str) and v.startswith("data:"):
            mime, blob = parse_data_url(v)
            sets += [f"{blobcol}=%s", f"{mimecol}=%s", f"{namecol}=%s"]
            vals += [blob, mime, data.get(jname)]
    if not sets:
        return
    vals.append(int(id))
    conn = conectar()
    try:
        conn.cursor().execute(f"UPDATE {store} SET {', '.join(sets)} WHERE id=%s", vals)
    finally:
        conn.close()


def remover(store, id):
    conn = conectar()
    try:
        conn.cursor().execute(f"DELETE FROM {store} WHERE id=%s", (int(id),))
    finally:
        conn.close()


def backup():
    out = {"versao": 1, "gerado": datetime.datetime.now().isoformat(),
           "candidatos": [], "entrevistas": [], "contratacoes": []}
    conn = conectar()
    try:
        cur = conn.cursor()
        for store in ORDEM_TABELAS:
            cur.execute(f"SELECT {detail_select(store)} FROM {store} ORDER BY id")
            out[store] = [row_to_detail(store, r) for r in cur.fetchall()]
    finally:
        conn.close()
    return out


def restaurar(payload):
    conn = conectar(autocommit=False)
    try:
        cur = conn.cursor()
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for store in ["entrevistas", "contratacoes", "candidatos"]:
            cur.execute(f"DELETE FROM {store}")
        for store in ORDEM_TABELAS:
            for rec in payload.get(store, []) or []:
                _insert(cur, store, rec)
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silencia log verboso; erros ainda aparecem via _erro

    def _send(self, code, obj=None, ctype="application/json", extra_headers=None):
        if obj is None:
            body = b""
        elif isinstance(obj, (bytes, bytearray)):
            body = bytes(obj)
        else:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _erro(self, code, msg):
        self._send(code, {"erro": msg})

    # ---- sessão ----
    def _token(self):
        bruto = self.headers.get("Cookie")
        if not bruto:
            return None
        try:
            ck = http.cookies.SimpleCookie(bruto)
            return ck["rh_sessao"].value if "rh_sessao" in ck else None
        except Exception:
            return None

    def _sessao(self):
        return sessao_valida(self._token() or "")

    def _exige_login(self):
        """Retorna a sessão; se não houver, responde 401 e retorna None."""
        s = self._sessao()
        if not s:
            self._erro(401, "Nao autenticado")
            return None
        return s

    def _cookie_login(self, token):
        return [("Set-Cookie",
                 f"rh_sessao={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age={SESSAO_HORAS * 3600}")]

    def _cookie_logout(self):
        return [("Set-Cookie", "rh_sessao=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0")]

    def _corpo(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _partes(self):
        return [p for p in self.path.split("?")[0].split("/") if p]

    def _servir_html(self):
        try:
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html")
        except FileNotFoundError:
            self._erro(404, "index.html nao encontrado")

    def do_GET(self):
        p = self._partes()
        if not p or p == ["index.html"]:
            return self._servir_html()
        try:
            # --- rotas públicas de autenticação ---
            if p == ["api", "setup"]:
                return self._send(200, {"precisaSetup": contar_usuarios() == 0})
            if p == ["api", "me"]:
                s = self._sessao()
                return self._send(200, {"usuario": s["usuario"]}) if s else self._erro(401, "Nao autenticado")

            # --- daqui para baixo exige login ---
            if not self._exige_login():
                return
            if p == ["api", "usuarios"]:
                return self._send(200, listar_usuarios())
            if p == ["api", "backup"]:
                return self._send(200, backup())
            if len(p) >= 2 and p[0] == "api" and p[1] in STORES:
                store = p[1]
                if len(p) == 2:
                    return self._send(200, listar(store))
                if len(p) == 3:
                    obj = obter(store, int(p[2]))
                    return self._send(200, obj) if obj else self._erro(404, "nao encontrado")
            return self._erro(404, "rota nao encontrada")
        except Exception as e:
            return self._erro(500, str(e))

    def do_POST(self):
        p = self._partes()
        try:
            # --- login (público) ---
            if p == ["api", "login"]:
                d = self._corpo()
                u = buscar_usuario((d.get("usuario") or "").strip())
                if u and verificar_senha(d.get("senha") or "", u["senha_hash"]):
                    token = criar_sessao(u["id"], u["nome"])
                    return self._send(200, {"usuario": u["nome"]}, extra_headers=self._cookie_login(token))
                return self._erro(401, "Usuario ou senha invalidos.")

            if p == ["api", "logout"]:
                tok = self._token()
                if tok:
                    SESSOES.pop(tok, None)
                return self._send(200, {"ok": True}, extra_headers=self._cookie_logout())

            # --- criar usuário: público SÓ no primeiro acesso (nenhum usuário ainda) ---
            if p == ["api", "usuarios"]:
                primeiro = contar_usuarios() == 0
                if not primeiro and not self._exige_login():
                    return
                d = self._corpo()
                novo_id = criar_usuario(d.get("usuario"), d.get("senha"))
                # No primeiro acesso, já loga o usuário recém-criado.
                if primeiro:
                    token = criar_sessao(novo_id, d.get("usuario").strip())
                    return self._send(201, {"id": novo_id, "usuario": d.get("usuario").strip()},
                                      extra_headers=self._cookie_login(token))
                return self._send(201, {"id": novo_id})

            # --- daqui para baixo exige login ---
            if not self._exige_login():
                return
            if p == ["api", "restore"]:
                restaurar(self._corpo())
                return self._send(200, {"ok": True})
            if len(p) == 2 and p[0] == "api" and p[1] in STORES:
                novo_id = criar(p[1], self._corpo())
                return self._send(201, {"id": novo_id})
            return self._erro(404, "rota nao encontrada")
        except ValueError as e:
            return self._erro(400, str(e))
        except Exception as e:
            return self._erro(500, str(e))

    def do_PUT(self):
        p = self._partes()
        try:
            if not self._exige_login():
                return
            if len(p) == 3 and p[0] == "api" and p[1] == "usuarios":
                alterar_senha(int(p[2]), (self._corpo().get("senha") or ""))
                return self._send(200, {"ok": True})
            if len(p) == 3 and p[0] == "api" and p[1] in STORES:
                atualizar(p[1], int(p[2]), self._corpo())
                return self._send(200, {"id": int(p[2])})
            return self._erro(404, "rota nao encontrada")
        except ValueError as e:
            return self._erro(400, str(e))
        except Exception as e:
            return self._erro(500, str(e))

    def do_DELETE(self):
        p = self._partes()
        try:
            if not self._exige_login():
                return
            if len(p) == 3 and p[0] == "api" and p[1] == "usuarios":
                excluir_usuario(int(p[2]))
                return self._send(200, {"ok": True})
            if len(p) == 3 and p[0] == "api" and p[1] in STORES:
                remover(p[1], int(p[2]))
                return self._send(200, {"ok": True})
            return self._erro(404, "rota nao encontrada")
        except ValueError as e:
            return self._erro(400, str(e))
        except Exception as e:
            return self._erro(500, str(e))


def ip_da_rede():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def esperar_mysql(tentativas, intervalo):
    """No boot o MySQL pode ainda nao estar pronto — tenta algumas vezes antes de desistir."""
    erro = None
    for i in range(1, tentativas + 1):
        try:
            conectar().close()
            return True, None
        except Exception as e:
            erro = e
            if i < tentativas:
                print(f"  MySQL ainda indisponivel (tentativa {i}/{tentativas}); "
                      f"nova tentativa em {intervalo}s...")
                time.sleep(intervalo)
    return False, erro


def main():
    if MODO_SERVICO:
        print("\n" + "=" * 60)
        print("Iniciando em " + datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    # 1) Conecta no MySQL (com espera, pois no boot ele pode demorar a subir)
    tentativas = 30 if MODO_SERVICO else 1   # servico: espera ate ~2,5 min
    ok, e = esperar_mysql(tentativas, 5)
    if not ok:
        print("=" * 60)
        print("ERRO ao conectar no MySQL:")
        print("  ", e)
        print("-" * 60)
        print("Verifique o arquivo config.json (usuario/senha/banco).")
        print("O banco 'sistema_rh' precisa existir (rode schema.sql).")
        print("=" * 60)
        if not MODO_SERVICO:
            input("Pressione Enter para fechar...")
        sys.exit(1)

    # 2) Garante colunas auxiliares
    ensure_schema()

    porta = int(SRV.get("port", 8080))
    host = SRV.get("host", "0.0.0.0")
    ip = ip_da_rede()
    print("=" * 60)
    print("  Sistema de RH — servidor iniciado")
    print("=" * 60)
    print(f"  Neste computador:   http://localhost:{porta}")
    print(f"  Nos outros PCs:     http://{ip}:{porta}")
    print(f"  Banco de dados:     {DB['database']} @ {DB['host']}")
    print("-" * 60)
    if MODO_SERVICO:
        print("  Rodando como servico (inicia junto com o Windows).")
    else:
        print("  Deixe esta janela ABERTA enquanto usar o sistema.")
        print("  Para parar: feche a janela ou pressione Ctrl+C")
    print("=" * 60)
    servidor = ThreadingHTTPServer((host, porta), Handler)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
