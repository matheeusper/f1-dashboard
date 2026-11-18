"""Historico permanente das suas voltas (SQLite, arquivo dados/historico.sqlite3).

Guarda cada volta lancada, o trecho de cada curva e o motivo das perdas, alem
do recorde de cada pista com a telemetria completa da volta (usada como
referencia nas proximas sessoes).
"""
import json
import os
import sqlite3
import statistics
import time
from array import array
from collections import Counter, defaultdict

from analise import Trace

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
ARQUIVO = os.path.join(PASTA, "historico.sqlite3")

ESQUEMA = """
create table if not exists sessoes(
  id integer primary key, uid text unique, inicio real, pista_key text, pista text,
  tipo text, corrida integer);
create table if not exists voltas(
  id integer primary key, sessao_id integer, num integer, tempo_ms integer,
  valida integer, composto integer, quando real);
create table if not exists curvas(
  volta_id integer, n integer, seg_ms integer, perda_ms integer, motivos text);
create table if not exists referencias(
  pista_key text primary key, tempo_ms integer, curvas text, traco blob,
  amostras integer, comprimento real, quando real);
create table if not exists pit_perdas(pista_key text, perda real, quando real);
create table if not exists conquistas(pista_key text, sessao_id integer, texto text, quando real);
create index if not exists ix_voltas_sessao on voltas(sessao_id);
create index if not exists ix_curvas_volta on curvas(volta_id);
create index if not exists ix_sessoes_pista on sessoes(pista_key);
"""


def conectar(caminho=ARQUIVO):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    db = sqlite3.connect(caminho, check_same_thread=False, timeout=5)
    db.execute("pragma journal_mode=wal")
    db.executescript(ESQUEMA)
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


class Historico:
    def __init__(self, caminho=ARQUIVO):
        self.db = conectar(caminho)

    # ------------------------------------------------------------ escrita
    def sessao(self, uid, chave, pista, tipo, corrida):
        self.db.execute("insert or ignore into sessoes(uid, inicio, pista_key, pista, tipo, corrida) "
                        "values (?,?,?,?,?,?)", (str(uid), time.time(), chave, pista, tipo, int(corrida)))
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

    def salvar_referencia(self, chave, tempo, curvas, tr, comprimento):
        self.db.execute("insert or replace into referencias values (?,?,?,?,?,?,?)",
                        (chave, int(tempo), json.dumps(curvas), _blob(tr), len(tr), comprimento,
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

    def referencia(self, chave):
        row = self.db.execute("select tempo_ms, curvas, traco, amostras, comprimento from referencias "
                              "where pista_key=?", (chave,)).fetchone()
        if not row:
            return None
        return {"tempo": row[0], "curvas": json.loads(row[1]), "traco": _traco(row[2], row[3]),
                "comprimento": row[4]}

    def resumo(self, chave, sessao_id, n_curvas):
        """O que o engenheiro sabe de voce nesta pista."""
        db = self.db
        r = {"voltas": 0, "sessoes": 0, "ideal": 0, "habitos": {}, "fraca": None, "fraca_ganho": 0,
             "anterior": None, "melhores_seg": {}}
        r["voltas"], r["sessoes"] = db.execute(
            "select count(v.id), count(distinct s.id) from sessoes s join voltas v on v.sessao_id=s.id "
            "where s.pista_key=?", (chave,)).fetchone()
        if n_curvas:
            melhores = dict(db.execute(
                "select c.n, min(c.seg_ms) from curvas c join voltas v on c.volta_id=v.id "
                "join sessoes s on v.sessao_id=s.id where s.pista_key=? and v.valida=1 group by c.n",
                (chave,)).fetchall())
            r["melhores_seg"] = melhores
            if len(melhores) == n_curvas:
                r["ideal"] = sum(melhores.values())
            # vicios: motivos mais repetidos nas ultimas 40 voltas
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
                "and v.valida=1 order by v.id desc limit 20", (chave,))]
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
            "and v.sessao_id<>? and v.valida=1 group by v.sessao_id having count(*)>=3 "
            "order by v.sessao_id desc limit 1", (chave, sessao_id or -1)).fetchone()
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
        return [{"key": r[0], "pista": r[1], "sessoes": r[2], "voltas": r[3], "recorde": r[4] or 0,
                 "ultima": r[5]} for r in rows]
    finally:
        db.close()


def api_evolucao(chave, caminho=ARQUIVO):
    db = conectar(caminho)
    try:
        pista = db.execute("select max(pista) from sessoes where pista_key=?", (chave,)).fetchone()[0]
        sessoes = []
        for sid, inicio, tipo in db.execute(
                "select id, inicio, tipo from sessoes where pista_key=? order by inicio", (chave,)).fetchall():
            linhas = db.execute("select tempo_ms, valida from voltas where sessao_id=?", (sid,)).fetchall()
            if not linhas:
                continue
            validas = [t for t, ok in linhas if ok]
            media, desvio = _media_limpa(validas)
            sessoes.append({"id": sid, "inicio": inicio, "tipo": tipo, "voltas": len(linhas),
                            "validas": len(validas), "melhor": min(validas) if validas else 0,
                            "media": round(media), "desvio": round(desvio)})
        ref = db.execute("select tempo_ms, curvas from referencias where pista_key=?", (chave,)).fetchone()
        n_curvas = len(json.loads(ref[1])) if ref else 0
        h = Historico.__new__(Historico)
        h.db = db
        resumo = h.resumo(chave, None, n_curvas)
        curvas = []
        for n in range(1, n_curvas + 1):
            segs = [x[0] for x in db.execute(
                "select c.seg_ms from curvas c join voltas v on c.volta_id=v.id join sessoes s "
                "on v.sessao_id=s.id where s.pista_key=? and v.valida=1 and c.n=? order by v.id desc "
                "limit 20", (chave, n))]
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
            "select texto, quando from conquistas where pista_key=? order by quando desc limit 40", (chave,))]
        return {"key": chave, "pista": pista, "recorde": ref[0] if ref else 0, "ideal": resumo["ideal"],
                "voltas": resumo["voltas"], "sessoes": sessoes, "curvas": curvas, "conquistas": conquistas}
    finally:
        db.close()
