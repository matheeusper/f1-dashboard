// Overlay por cima do jogo (janela transparente do app nativo): posicao, delta, rivais, ERS,
// combustivel, a ultima mensagem do radio e o minissetor de cada curva. So mostra; nao fala.
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const E = { hud: $('hud'), pos: $('pos'), lap: $('lap'), delta: $('delta'), frente: $('frente'), atras: $('atras'),
    ers: $('ers'), fuel: $('fuel'), radio: $('radio'), msg: $('msg'), ms: $('ms') };
  const txt = (el, t) => { if (el.textContent !== t) el.textContent = t; };
  const seg = (ms) => DEC((ms / 1000).toFixed(1));
  let S = null, ultimaMsg = null, msgAte = 0, ultimoFlash = null, flashAte = 0;

  function nomeCurto(n) { return n.length > 10 ? n.slice(0, 9) + '.' : n; }

  function render() {
    const agora = performance.now();
    if (!S) return;
    E.hud.classList.toggle('off', !S.connected);
    const lap = S.lap, ses = S.session, st = S.status, c = S.coach || {};
    txt(E.pos, lap && lap.pos ? 'P' + lap.pos : '–');
    txt(E.lap, lap && lap.num ? lap.num + (ses && ses.isRace && ses.totalLaps ? '/' + ses.totalLaps : '') : '–');
    const dl = lap ? lap.delta : null;
    txt(E.delta, dl == null ? '—' : (dl < 0 ? '−' : '+') + DEC((Math.abs(dl) / 1000).toFixed(3)));
    E.delta.className = 'v' + (dl == null ? '' : dl < 0 ? ' neg' : ' pos');
    // rivais: o da frente e o de tras, pela torre
    const t = c.torre && c.torre.carros, eu = t && t.find((k) => k.eu);
    if (eu) {
      const f = t.find((k) => k.pos === eu.pos - 1 && !k.fora), a = t.find((k) => k.pos === eu.pos + 1 && !k.fora);
      txt(E.frente, f ? nomeCurto(f.nome) + ' ' + seg(eu.int) : '—');
      txt(E.atras, a ? nomeCurto(a.nome) + ' ' + seg(a.int) : '—');
    }
    if (st) {
      txt(E.ers, Math.round(st.ersStore / 4e4) + '%');
      E.ers.className = 'v' + (st.ersStore < 0.15 * 4e6 ? ' warn' : '');
      txt(E.fuel, (st.fuelLaps < 0 ? '−' : '+') + DEC(Math.abs(st.fuelLaps).toFixed(1)));
      E.fuel.className = 'v' + (st.fuelLaps < 0 ? ' pos' : '');
    }
    // ultima mensagem do radio
    const msgs = c.msgs || [];
    const m = msgs[msgs.length - 1];
    if (m && m.seq !== ultimaMsg) {
      if (ultimaMsg !== null || m.age < 3000) {
        txt(E.msg, m.show);
        E.radio.classList.toggle('p1', m.pri === 1);
        msgAte = agora + Math.min(12000, Math.max(5000, m.show.length * 70));
      }
      ultimaMsg = m.seq;
    }
    E.radio.classList.toggle('show', agora < msgAte);
    // minissetor da curva que acabou de fechar
    const fl = c.live && c.live.flash;
    if (fl && fl.seq !== ultimoFlash) {
      if (ultimoFlash !== null) {
        E.ms.innerHTML = '<small>' + T('CURVA ') + fl.n + '</small>' + (fl.d > 0 ? '+' : fl.d < 0 ? '−' : '') +
          DEC(Math.abs(fl.d).toFixed(3));
        E.ms.style.color = fl.d >= 0.06 ? 'var(--vermelho)' : fl.d <= -0.03 ? 'var(--verde)' : 'var(--texto)';
        flashAte = agora + 1800;
      }
      ultimoFlash = fl.seq;
    }
    E.ms.classList.toggle('show', agora < flashAte);
  }

  function conectar() {
    const es = new EventSource('/stream');
    es.onmessage = (e) => {
      S = JSON.parse(e.data);
      if (S.lang && S.lang !== (LANG_EN ? 'en' : 'pt')) location.reload();
    };
    es.onerror = () => { es.close(); S = null; E.hud.classList.add('off'); setTimeout(conectar, 2000); };
  }
  conectar();
  setInterval(render, 100);
})();
