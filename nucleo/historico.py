"""Historico permanente das suas voltas (SQLite, arquivo dados/historico.sqlite3).

Guarda cada volta lancada, o trecho de cada curva e o motivo das perdas, alem
do recorde de cada pista com a telemetria completa da volta (usada como
referencia nas proximas sessoes).

Recorde, volta ideal, ponto fraco e comparacao com a sessao anterior sao
separados por grupo de sessao: "rapida" (Time Trial e classificacao: pouco
combustivel e pneu novo) e "corrida" (corrida e treinos livres). Os vicios
(como voce erra cada curva) continuam somando tudo.
"""
import json
import os
import sqlite3
import statistics
import time
from array import array
from collections import Counter, defaultdict

from analise import Trace
from caminhos import DADOS
from f1_packets import SESSION_TYPES, grupo_da_sessao
from idioma import tx

PASTA = DADOS
ARQUIVO = os.path.join(PASTA, "historico.sqlite3")

ESQUEMA = """
create table if not exists sessoes(
  id integer primary key, uid text unique, inicio real, pista_key text, pista text,
  tipo text, corrida integer, grupo text);
create table if not exists voltas(
  id integer primary key, sessao_id integer, num integer, tempo_ms integer,
  valida integer, composto integer, quando real);
create table if not exists curvas(
  volta_id integer, n integer, seg_ms integer, perda_ms integer, motivos text);
create table if not exists referencias(
  pista_key text primary key, tempo_ms integer, curvas text, traco blob,
  amostras integer, comprimento real, quando real);
create table if not exists recordes(
  pista_key text, grupo text, tempo_ms integer, curvas text, traco blob,
  amostras integer, comprimento real, quando real, primary key(pista_key, grupo));
create table if not exists pit_perdas(pista_key text, perda real, quando real);
create table if not exists conquistas(pista_key text, sessao_id integer, texto text, quando real);
create index if not exists ix_voltas_sessao on voltas(sessao_id);
create index if not exists ix_curvas_volta on curvas(volta_id);
create index if not exists ix_sessoes_pista on sessoes(pista_key);
"""

RAPIDA, CORRIDA = "rapida", "corrida"
GRUPOS = (RAPIDA, CORRIDA)
VERSAO = 1   # pragma user_version: 1 = recordes separados por grupo


def _migrar(db):
    """Bancos antigos: grupo em cada sessao e o recorde unico vira o recorde do grupo onde foi feito."""
    if db.execute("pragma user_version").fetchone()[0] >= VERSAO:
        return
    colunas = [c[1] for c in db.execute("pragma table_info(sessoes)")]
    if "grupo" not in colunas:
        db.execute("alter table sessoes add column grupo text")
    for tid, nome in SESSION_TYPES.items():
        db.execute("update sessoes set grupo=? where grupo is null and tipo=?", (grupo_da_sessao(tid), nome))
    db.execute("update sessoes set grupo=? where grupo is null", (CORRIDA,))
    for chave, tempo, curvas, traco, amostras, comp, quando in db.execute(
            "select pista_key, tempo_ms, curvas, traco, amostras, comprimento, quando from referencias").fetchall():
        # a sessao da volta que virou recorde (mesmo tempo); se nao achar, a da melhor volta valida da pista
        g = db.execute("select s.grupo from voltas v join sessoes s on v.sessao_id=s.id where s.pista_key=? "
                       "and v.valida=1 order by (v.tempo_ms<>?), v.tempo_ms limit 1", (chave, tempo)).fetchone()
        db.execute("insert or ignore into recordes values (?,?,?,?,?,?,?,?)",
                   (chave, g[0] if g else CORRIDA, tempo, curvas, traco, amostras, comp, quando))
    db.execute("pragma user_version=%d" % VERSAO)


def conectar(caminho=ARQUIVO):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    db = sqlite3.connect(caminho, check_same_thread=False, timeout=5)
    db.execute("pragma journal_mode=wal")
    db.executescript(ESQUEMA)
    _migrar(db)
    db.commit()
    return db


def _blob(tr):
    return b"".join(getattr(tr, f).tobytes() for f in Trace.COMPLETO)


def _traco(blob, n):
    tr = Trace()
    tam = n * 4
    for i, f in enumerate(Trace.COMPLETO):
        a = array("f")
        pedaco = blob[i * tam:(i + 1) * tam]
        if len(pedaco) == tam:
            a.frombytes(pedaco)
        else:   # referencia gravada antes de existir este canal
            a.extend([0.0] * n)
        setattr(tr, f, a)
    return tr


def _media_limpa(tempos):
    """Media das voltas ate 107% da melhor (tira voltas com erro grosseiro)."""
    if not tempos:
        return 0, 0
    melhor = min(tempos)
    ok = [t for t in tempos if t <= melhor * 1.07]
    media = sum(ok) / len(ok)
    desvio = statistics.pstdev(ok) if len(ok) > 1 else 0
    return media, desvio


def _filtro(grupo):
    """Pedaco do where que limita ao grupo de sessao (None = todas)."""
    return (" and s.grupo=?", (grupo,)) if grupo else ("", ())


def _melhor_volta(db, chave, grupo):
    f, a = _filtro(grupo)
    row = db.execute("select min(v.tempo_ms) from voltas v join sessoes s on v.sessao_id=s.id "
                     "where s.pista_key=? and v.valida=1" + f, (chave,) + a).fetchone()
    return row[0] or 0


class Historico:
    def __init__(self, caminho=ARQUIVO):
        self.db = conectar(caminho)

    # ------------------------------------------------------------ escrita
    def sessao(self, uid, chave, pista, tipo, corrida, grupo):
        self.db.execute("insert or ignore into sessoes(uid, inicio, pista_key, pista, tipo, corrida, grupo) "
                        "values (?,?,?,?,?,?,?)",
                        (str(uid), time.time(), chave, pista, tipo, int(corrida), grupo))
        self.db.commit()
        return self.db.execute("select id from sessoes where uid=?", (str(uid),)).fetchone()[0]

    def salvar_volta(self, sessao_id, num, tempo, valida, composto, curvas):
        cur = self.db.execute("insert into voltas(sessao_id, num, tempo_ms, valida, composto, quando) "
                              "values (?,?,?,?,?,?)",
                              (sessao_id, num, int(tempo), int(valida), composto, time.time()))
        vid = cur.lastrowid
        self.db.executemany("insert into curvas(volta_id, n, seg_ms, perda_ms, motivos) values (?,?,?,?,?)",
                            [(vid, n, int(seg), None if perda is None else int(perda), motivos)
                             for n, seg, perda, motivos in curvas])
        self.db.commit()
        return vid

    def salvar_referencia(self, chave, grupo, tempo, curvas, tr, comprimento):
        self.db.execute("insert or replace into recordes values (?,?,?,?,?,?,?,?)",
                        (chave, grupo, int(tempo), json.dumps(curvas), _blob(tr), len(tr), comprimento,
                         time.time()))
        self.db.commit()

    def salvar_conquista(self, chave, sessao_id, texto):
        self.db.execute("insert into conquistas values (?,?,?,?)", (chave, sessao_id, texto, time.time()))
        self.db.commit()

    def salvar_perda_pit(self, chave, perda):
        self.db.execute("insert into pit_perdas values (?,?,?)", (chave, float(perda), time.time()))
        self.db.commit()

    # ------------------------------------------------------------ leitura
    def perdas_pit(self, chave, n=12):
        """Ultimas perdas de tempo medidas em pit stops nesta pista (segundos)."""
        return [x[0] for x in self.db.execute(
            "select perda from pit_perdas where pista_key=? order by quando desc limit ?", (chave, n))]

    def referencia(self, chave, grupo):
        """Recorde do grupo com a telemetria da volta, e as curvas da pista (iguais nos dois grupos).
        Grupo ainda sem telemetria salva: tempo = melhor volta valida dele e traco None."""
        rows = self.db.execute("select grupo, tempo_ms, curvas, traco, amostras, comprimento from recordes "
                               "where pista_key=? order by quando desc", (chave,)).fetchall()
        if not rows:
            return None
        meu = next((r for r in rows if r[0] == grupo), None)
        base = meu or rows[0]
        return {"tempo": meu[1] if meu else _melhor_volta(self.db, chave, grupo),
                "traco": _traco(meu[3], meu[4]) if meu else None,
                "curvas": json.loads(base[2]), "comprimento": base[5]}

    def resumo(self, chave, sessao_id, n_curvas, grupo=None):
        """O que o engenheiro sabe de voce nesta pista. Com grupo, o que depende de ritmo (melhores
        trechos, volta ideal, ponto fraco, sessao anterior) olha so as sessoes desse grupo."""
        db = self.db
        f, a = _filtro(grupo)
        r = {"voltas": 0, "sessoes": 0, "voltas_grupo": 0, "ideal": 0, "habitos": {}, "fraca": None,
             "fraca_ganho": 0, "anterior": None, "melhores_seg": {}}
        r["voltas"], r["sessoes"] = db.execute(
            "select count(v.id), count(distinct s.id) from sessoes s join voltas v on v.sessao_id=s.id "
            "where s.pista_key=?", (chave,)).fetchone()
        r["voltas_grupo"] = db.execute(
            "select count(v.id) from sessoes s join voltas v on v.sessao_id=s.id where s.pista_key=?" + f,
            (chave,) + a).fetchone()[0]
        if n_curvas:
            melhores = dict(db.execute(
                "select c.n, min(c.seg_ms) from curvas c join voltas v on c.volta_id=v.id "
                "join sessoes s on v.sessao_id=s.id where s.pista_key=? and v.valida=1" + f + " group by c.n",
                (chave,) + a).fetchall())
            r["melhores_seg"] = melhores
            if len(melhores) == n_curvas:
                r["ideal"] = sum(melhores.values())
            # vicios: motivos mais repetidos nas ultimas 40 voltas (de qualquer grupo: e o jeito de pilotar)
            ids = [x[0] for x in db.execute(
                "select v.id from voltas v join sessoes s on v.sessao_id=s.id where s.pista_key=? "
                "order by v.id desc limit 40", (chave,))]
            if ids:
                marcas = ",".join("?" * len(ids))
                cont = defaultdict(Counter)
                for n, motivos in db.execute(
                        "select n, motivos from curvas where volta_id in (%s)" % marcas, ids):
                    for m in (motivos or "").split(","):
                        if m and m != "geral":
                            cont[n][m] += 1
                for n, c in cont.items():
                    m, q = c.most_common(1)[0]
                    if q >= 4 and q / len(ids) >= 0.3:
                        r["habitos"][n] = [m, round(q / len(ids), 2), q, len(ids)]
            # ponto fraco: maior distancia entre a media recente e o seu melhor trecho
            ids_v = [x[0] for x in db.execute(
                "select v.id from voltas v join sessoes s on v.sessao_id=s.id where s.pista_key=? "
                "and v.valida=1" + f + " order by v.id desc limit 20", (chave,) + a)]
            if len(ids_v) >= 3 and melhores:
                marcas = ",".join("?" * len(ids_v))
                medias = dict(db.execute("select n, avg(seg_ms) from curvas where volta_id in (%s) "
                                         "group by n" % marcas, ids_v).fetchall())
                ganhos = {n: medias[n] - melhores[n] for n in medias if n in melhores}
                if ganhos:
                    n = max(ganhos, key=ganhos.get)
                    r["fraca"], r["fraca_ganho"] = n, ganhos[n]
        ant = db.execute(
            "select v.sessao_id from voltas v join sessoes s on v.sessao_id=s.id where s.pista_key=? "
            "and v.sessao_id<>? and v.valida=1" + f + " group by v.sessao_id having count(*)>=3 "
            "order by v.sessao_id desc limit 1", (chave, sessao_id or -1) + a).fetchone()
        if ant:
            tempos = [x[0] for x in db.execute("select tempo_ms from voltas where sessao_id=? and valida=1",
                                               (ant[0],))]
            media, desvio = _media_limpa(tempos)
            r["anterior"] = {"id": ant[0], "melhor": min(tempos), "media": media, "desvio": desvio,
                             "voltas": len(tempos)}
        return r

    def comparar_sessoes(self, sessao_id, anterior_id):
        """Media de cada trecho nesta sessao e na anterior (so voltas validas)."""
        def medias(sid):
            return dict(self.db.execute(
                "select c.n, avg(c.seg_ms) from curvas c join voltas v on c.volta_id=v.id "
                "where v.sessao_id=? and v.valida=1 group by c.n", (sid,)).fetchall())
        return medias(sessao_id), medias(anterior_id)


# ---------------------------------------------------------------- pagina Evolucao
def api_pistas(caminho=ARQUIVO):
    db = conectar(caminho)
    try:
        rows = db.execute(
            "select s.pista_key, max(s.pista), count(distinct s.id), count(v.id), "
            "min(case when v.valida=1 then v.tempo_ms end), max(s.inicio) "
            "from sessoes s join voltas v on v.sessao_id=s.id group by s.pista_key "
            "order by max(s.inicio) desc").fetchall()
        return [{"key": r[0], "pista": tx(r[1]), "sessoes": r[2], "voltas": r[3], "recorde": r[4] or 0,
                 "ultima": r[5]} for r in rows]
    finally:
        db.close()


def api_evolucao(chave, caminho=ARQUIVO, grupo=None):
    """Historico de uma pista. grupo = "rapida", "corrida" ou None (tudo junto)."""
    grupo = grupo if grupo in GRUPOS else None
    f, a = _filtro(grupo)
    db = conectar(caminho)
    try:
        pista = db.execute("select max(pista) from sessoes where pista_key=?", (chave,)).fetchone()[0]
        sessoes, por_grupo, ultimo = [], dict.fromkeys(GRUPOS, 0), None
        for sid, inicio, tipo, g in db.execute(
                "select id, inicio, tipo, grupo from sessoes where pista_key=? order by inicio", (chave,)).fetchall():
            linhas = db.execute("select tempo_ms, valida from voltas where sessao_id=?", (sid,)).fetchall()
            if not linhas:
                continue
            por_grupo[g] = por_grupo.get(g, 0) + 1
            ultimo = g
            if grupo and g != grupo:
                continue
            validas = [t for t, ok in linhas if ok]
            media, desvio = _media_limpa(validas)
            sessoes.append({"id": sid, "inicio": inicio, "tipo": tx(tipo), "grupo": g, "voltas": len(linhas),
                            "validas": len(validas), "melhor": min(validas) if validas else 0,
                            "media": round(media), "desvio": round(desvio)})
        ref = db.execute("select curvas from recordes where pista_key=? order by quando desc limit 1",
                         (chave,)).fetchone()
        n_curvas = len(json.loads(ref[0])) if ref else 0
        h = Historico.__new__(Historico)
        h.db = db
        resumo = h.resumo(chave, None, n_curvas, grupo)
        curvas = []
        for n in range(1, n_curvas + 1):
            segs = [x[0] for x in db.execute(
                "select c.seg_ms from curvas c join voltas v on c.volta_id=v.id join sessoes s "
                "on v.sessao_id=s.id where s.pista_key=? and v.valida=1 and c.n=?" + f + " order by v.id desc "
                "limit 20", (chave, n) + a)]
            if not segs:
                continue
            recentes, antigas = segs[:10], segs[10:]
            melhor = resumo["melhores_seg"].get(n, min(segs))
            media = sum(recentes) / len(recentes)
            tend = (media - sum(antigas) / len(antigas)) if antigas else None
            hab = resumo["habitos"].get(n)
            curvas.append({"n": n, "melhor": melhor, "media": round(media), "ganho": round(media - melhor),
                           "tendencia": None if tend is None else round(tend),
                           "habito": hab[0] if hab else None, "habito_pct": hab[1] if hab else 0})
        conquistas = [{"texto": t, "quando": q} for t, q in db.execute(
            "select c.texto, c.quando from conquistas c left join sessoes s on c.sessao_id=s.id "
            "where c.pista_key=?" + (" and (s.grupo=? or s.grupo is null)" if grupo else "") +
            " order by c.quando desc limit 40", (chave,) + a)]
        return {"key": chave, "pista": tx(pista), "grupo": grupo or "", "grupos": por_grupo, "ultimo": ultimo,
                "recorde": _melhor_volta(db, chave, grupo), "ideal": resumo["ideal"],
                "voltas": resumo["voltas_grupo"], "sessoes": sessoes, "curvas": curvas, "conquistas": conquistas}
    finally:
        db.close()
