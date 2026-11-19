// Pagina Evolucao: historico de voltas por pista (dados de /api/pistas e /api/evolucao).
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const sel = $('pista'), selGrupo = $('grupo'), box = $('conteudo');
  // recorde, volta ideal e evolucao separados: TT/classificacao (pouco combustivel) x corrida/treino
  const GRUPOS = [
    ['rapida', T('Volta rápida (TT e classificação)')],
    ['corrida', T('Corrida e treinos')],
    ['', T('Tudo junto')],
  ];
  let grupo = null;   // null = ainda nao escolhido: abre no grupo da ultima sessao da pista
  try { grupo = localStorage.getItem('painel.grupo'); } catch (e) { /* sem storage */ }
  // aberta dentro do painel (menu > Evolucao): o painel ja tem o botao de fechar e o titulo
  if (window.top !== window) {
    for (const el of document.querySelectorAll('.back, h1')) el.style.display = 'none';
  }
  const HABITO = {
    trava: T('travar as rodas'), cedo: T('frear cedo demais'), tarde: T('frear tarde e passar do ponto'),
    lento: T('contornar devagar demais'), acel: T('acelerar tarde na saída'), patinou: T('patinar na saída'),
    rapido: T('entrar rápido demais'),
  };
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);

  function fmtLap(ms) {
    if (!ms || ms <= 0) return '—';
    const m = Math.floor(ms / 60000), s = (ms % 60000) / 1000;
    return m + ':' + (s < 10 ? '0' : '') + s.toFixed(3);
  }
  const fmtSeg = (ms) => DEC((ms / 1000).toFixed(3));
  const fmtDia = (t) => {
    const d = new Date(t * 1000);
    return d.toLocaleDateString(LOCALE, { day: '2-digit', month: '2-digit' }) + ' ' +
      d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' });
  };

  function grafico(sessoes) {
    const pts = sessoes.filter((s) => s.melhor > 0);
    if (pts.length < 2) {
      return '<div class="empty" style="padding:30px">' + T('O gráfico aparece a partir da segunda sessão nesta pista.') + '</div>';
    }
    const W = 1000, H = 360, L = 86, Rm = 20, Tm = 20, B = 46;   // margens (Tm = topo)
    const vals = pts.flatMap((s) => [s.melhor, s.media]).filter((v) => v > 0);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max(200, (hi - lo) * 0.15);
    lo -= pad; hi += pad;
    const x = (i) => L + (W - L - Rm) * (pts.length === 1 ? 0.5 : i / (pts.length - 1));
    const y = (v) => Tm + (H - Tm - B) * (1 - (v - lo) / (hi - lo));
    let g = '';
    for (let k = 0; k <= 4; k++) {
      const v = lo + (hi - lo) * k / 4;
      g += '<line class="axis" x1="' + L + '" x2="' + (W - Rm) + '" y1="' + y(v) + '" y2="' + y(v) + '"/>' +
        '<text class="axis-t" x="' + (L - 10) + '" y="' + (y(v) + 4) + '" text-anchor="end">' + fmtLap(Math.round(v)) + '</text>';
    }
    const passo = Math.max(1, Math.ceil(pts.length / 7));
    const dias = new Set(pts.map((s) => fmtDia(s.inicio).split(' ')[0]));
    pts.forEach((s, i) => {
      if (i % passo === 0 || i === pts.length - 1) {
        const [dia, hora] = fmtDia(s.inicio).split(' ');
        const rot = dias.size < pts.length ? dia + ' ' + hora : dia;   // varias sessoes no mesmo dia: mostra a hora
        const anc = i === 0 ? 'start' : i === pts.length - 1 ? 'end' : 'middle';
        g += '<text class="axis-t" x="' + x(i) + '" y="' + (H - 16) + '" text-anchor="' + anc + '">' + rot + '</text>';
      }
    });
    const linha = (k) => pts.map((s, i) => x(i).toFixed(1) + ',' + y(s[k]).toFixed(1)).join(' ');
    g += '<polyline class="l-avg" points="' + linha('media') + '"/>';
    g += '<polyline class="l-best" points="' + linha('melhor') + '"/>';
    pts.forEach((s, i) => {
      g += '<circle class="d-avg" cx="' + x(i) + '" cy="' + y(s.media) + '" r="4"><title>' + T('Média ') + fmtLap(s.media) + '</title></circle>';
      g += '<circle class="d-best" cx="' + x(i) + '" cy="' + y(s.melhor) + '" r="6"><title>' + T('Melhor ') + fmtLap(s.melhor) + ' · ' + fmtDia(s.inicio) + '</title></circle>';
    });
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + T('Melhor volta e média por sessão') + '">' + g + '</svg>' +
      '<div class="legend"><span><i style="background:var(--purple)"></i>' + T('Melhor volta da sessão') + '</span>' +
      '<span><i style="background:var(--cyan)"></i>' + T('Média das voltas limpas') + '</span></div>';
  }

  function render(d) {
    if (!d.sessoes.length) {
      box.innerHTML = '<div class="panel empty">' + T('Nenhuma volta registrada nesta pista ainda.') + '</div>';
      return;
    }
    const ult = d.sessoes[d.sessoes.length - 1];
    const potencial = d.recorde && d.ideal ? d.recorde - d.ideal : 0;
    let h = '<div class="cards">' +
      '<div class="panel card"><span class="lbl">' + T('Recorde pessoal') + '</span><b class="p">' + fmtLap(d.recorde) + '</b><small>' + T('sua melhor volta aqui') + '</small></div>' +
      '<div class="panel card"><span class="lbl">' + T('Volta ideal') + '</span><b class="c">' + fmtLap(d.ideal) + '</b><small>' +
      (potencial > 0 ? T('seus melhores trechos somados: %s s para buscar').replace('%s', fmtSeg(potencial)) : T('soma dos seus melhores trechos')) + '</small></div>' +
      '<div class="panel card"><span class="lbl">' + T('Última sessão') + '</span><b>' + fmtLap(ult.melhor) + '</b><small>' + T('média ') + fmtLap(ult.media) +
      ' · ±' + fmtSeg(ult.desvio) + ' s</small></div>' +
      '<div class="panel card"><span class="lbl">' + T('Voltas registradas') + '</span><b>' + d.voltas + '</b><small>' + (d.sessoes.length === 1 ? T('em 1 sessão') : T('em %d sessões').replace('%d', d.sessoes.length)) + '</small></div>' +
      '</div>';
    h += '<div class="panel"><h2>' + T('EVOLUÇÃO POR SESSÃO') + '</h2>' + grafico(d.sessoes) + '</div>';
    if (d.conquistas && d.conquistas.length) {
      h += '<div class="panel"><h2>' + T('CONQUISTAS DO MODO TREINO') + ' (' + d.conquistas.length + ')</h2><ul class="conq">' +
        d.conquistas.map((c) => '<li><span>🏆 ' + esc(c.texto) + '</span><span class="quando">' + fmtDia(c.quando) +
          '</span></li>').join('') + '</ul></div>';
    }

    if (d.curvas.length) {
      const maxG = Math.max(...d.curvas.map((c) => c.ganho), 1);
      const piores = d.curvas.slice().sort((a, b) => b.ganho - a.ganho).slice(0, 3).map((c) => c.n);
      h += '<div class="panel"><h2>' + T('CURVA A CURVA') + '</h2><div class="scroll"><table><thead><tr>' +
        '<th>' + T('CURVA') + '</th><th>' + T('MELHOR TRECHO') + '</th><th>' + T('MÉDIA RECENTE') + '</th><th>' + T('TEMPO PARA BUSCAR') + '</th><th>' + T('TENDÊNCIA') + '</th><th>' + T('VÍCIO') + '</th>' +
        '</tr></thead><tbody>' + d.curvas.map((c) => {
          const t = c.tendencia == null ? '—' : Math.abs(c.tendencia) < 15 ? T('estável')
            : c.tendencia < 0 ? '<span class="down">▼ ' + fmtSeg(-c.tendencia) + T(' s melhor') + '</span>'
              : '<span class="up">▲ ' + fmtSeg(c.tendencia) + T(' s pior') + '</span>';
          const hab = c.habito ? '<span class="habit">' + esc(HABITO[c.habito] || c.habito) + ' (' + Math.round(c.habito_pct * 100) + T('% das voltas') + ')</span>' : '—';
          return '<tr><td><b>' + c.n + '</b>' + (piores.includes(c.n) && c.ganho > 40 ? ' <span class="up">●</span>' : '') +
            '</td><td>' + fmtSeg(c.melhor) + ' s</td><td>' + fmtSeg(c.media) + ' s</td><td><span class="bar"><i style="transform:scaleX(' +
            (c.ganho / maxG).toFixed(3) + ')"></i></span>' + fmtSeg(c.ganho) + ' s</td><td>' + t + '</td><td class="wrap">' + hab + '</td></tr>';
        }).join('') + '</tbody></table></div>' +
        '<div class="legend">' + T('Tendência compara suas 10 últimas voltas limpas com as 10 anteriores. ● = onde você mais tem tempo para ganhar.') + '</div></div>';
    }

    h += '<div class="panel"><h2>' + T('SESSÕES') + '</h2><div class="scroll"><table><thead><tr>' +
      '<th>' + T('DATA') + '</th><th>' + T('TIPO') + '</th><th>' + T('VOLTAS') + '</th><th>' + T('MELHOR') + '</th><th>' + T('MÉDIA') + '</th><th>' + T('CONSISTÊNCIA') + '</th></tr></thead><tbody>' +
      d.sessoes.slice().reverse().map((s) => '<tr><td>' + fmtDia(s.inicio) + '</td><td>' + esc(s.tipo || '—') + '</td><td>' +
        s.validas + ' / ' + s.voltas + '</td><td>' + (s.melhor === d.recorde ? '<b style="color:var(--purple)">' + fmtLap(s.melhor) + '</b>' : fmtLap(s.melhor)) +
        '</td><td>' + fmtLap(s.media) + '</td><td>±' + fmtSeg(s.desvio) + ' s</td></tr>').join('') +
      '</tbody></table></div></div>';
    box.innerHTML = h;
  }

  function opcoesGrupo(d) {
    const n = d.grupos || {};
    const total = (n.rapida || 0) + (n.corrida || 0);
    selGrupo.innerHTML = GRUPOS.map(([k, nome]) => {
      const q = k ? n[k] || 0 : total;
      return '<option value="' + k + '"' + (q ? '' : ' disabled') + '>' + esc(nome) + ' · ' +
        (q === 1 ? T('1 sessão') : T('%d sessões').replace('%d', q)) + '</option>';
    }).join('');
    selGrupo.value = d.grupo;
    selGrupo.style.display = '';
  }

  function carregar(chave) {
    try { localStorage.setItem('painel.pista', chave); } catch (e) { /* sem storage */ }
    const pede = grupo == null ? '' : grupo;
    fetch('/api/evolucao?pista=' + encodeURIComponent(chave) + '&grupo=' + encodeURIComponent(pede))
      .then((r) => r.json()).then((d) => {
        // primeira vez, ou o grupo escolhido nao tem sessoes nesta pista: vai para o da ultima sessao
        const vazio = d.grupo && !(d.grupos || {})[d.grupo];
        if ((grupo == null || vazio) && d.ultimo && d.ultimo !== d.grupo) {
          if (grupo == null) grupo = d.ultimo;
          return fetch('/api/evolucao?pista=' + encodeURIComponent(chave) + '&grupo=' + d.ultimo).then((r) => r.json());
        }
        return d;
      }).then((d) => { opcoesGrupo(d); render(d); })
      .catch(() => { box.innerHTML = '<div class="panel empty">' + T('Não consegui ler o histórico. O servidor do painel está aberto?') + '</div>'; });
  }

  selGrupo.addEventListener('change', () => {
    grupo = selGrupo.value;
    try { localStorage.setItem('painel.grupo', grupo); } catch (e) { /* sem storage */ }
    carregar(sel.value);
  });

  fetch('/api/pistas').then((r) => r.json()).then((pistas) => {
    if (!pistas.length) {
      sel.style.display = 'none';
      box.innerHTML = '<div class="panel empty">' + T('Nenhuma volta registrada ainda.') + '<br>' + T('Corra no F1 25 com o painel aberto: cada volta limpa entra aqui automaticamente.') + '</div>';
      return;
    }
    let salvo = null;
    try { salvo = localStorage.getItem('painel.pista'); } catch (e) { /* sem storage */ }
    sel.innerHTML = pistas.map((p) => '<option value="' + esc(p.key) + '">' + esc(p.pista) + ' · ' + p.voltas + T(' voltas') + '</option>').join('');
    if (salvo && pistas.some((p) => p.key === salvo)) sel.value = salvo;
    sel.addEventListener('change', () => carregar(sel.value));
    carregar(sel.value);
  }).catch(() => { box.innerHTML = '<div class="panel empty">' + T('Não consegui ler o histórico. O servidor do painel está aberto?') + '</div>'; });

  addEventListener('keydown', (e) => { if (e.key === 'Escape' || e.key.toLowerCase() === 'p') location.href = '/'; });
})();
