# -*- coding: utf-8 -*-
# ============================================================
#  Sistema de RH — Back-end (Python + MySQL)
#  Serve a pagina index.html e expoe uma API que le/grava no MySQL.
#  Rodar:  python server.py   (ou dois cliques em iniciar-servidor.bat)
# ============================================================
import json, base64, os, sys, socket, datetime, time
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
        "scalars": [("candId", "cand_id"), ("data", "data"), ("situacao", "situacao"),
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
INT_COLS = {"cand_id", "prazo"}


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


def ensure_schema():
    """Garante as colunas de mime (para reconstruir os anexos)."""
    conn = conectar()
    try:
        cur = conn.cursor()
        add_col_if_missing(cur, "candidatos", "curriculo_mime", "VARCHAR(120) NULL")
        add_col_if_missing(cur, "entrevistas", "formulario_mime", "VARCHAR(120) NULL")
    finally:
        conn.close()


# ---------- Conversoes ----------
def to_json_value(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()[:10] if isinstance(v, datetime.date) and not isinstance(v, datetime.datetime) else v.isoformat()
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

    def _send(self, code, obj=None, ctype="application/json"):
        if obj is None:
            body = b""
        elif isinstance(obj, (bytes, bytearray)):
            body = bytes(obj)
        else:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _erro(self, code, msg):
        self._send(code, {"erro": msg})

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
            if p == ["api", "restore"]:
                restaurar(self._corpo())
                return self._send(200, {"ok": True})
            if len(p) == 2 and p[0] == "api" and p[1] in STORES:
                novo_id = criar(p[1], self._corpo())
                return self._send(201, {"id": novo_id})
            return self._erro(404, "rota nao encontrada")
        except Exception as e:
            return self._erro(500, str(e))

    def do_PUT(self):
        p = self._partes()
        try:
            if len(p) == 3 and p[0] == "api" and p[1] in STORES:
                atualizar(p[1], int(p[2]), self._corpo())
                return self._send(200, {"id": int(p[2])})
            return self._erro(404, "rota nao encontrada")
        except Exception as e:
            return self._erro(500, str(e))

    def do_DELETE(self):
        p = self._partes()
        try:
            if len(p) == 3 and p[0] == "api" and p[1] in STORES:
                remover(p[1], int(p[2]))
                return self._send(200, {"ok": True})
            return self._erro(404, "rota nao encontrada")
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
