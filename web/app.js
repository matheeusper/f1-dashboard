// Painel F1 25 — recebe o estado do carro por SSE (/stream) e desenha a tela.
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const stage = $('stage');

  // ------------------------------------------------------------ utilitarios
  const txt = (el, v) => { if (el._t !== v) { el._t = v; el.textContent = v; } };
  const html = (el, v) => { if (el._h !== v) { el._h = v; el.innerHTML = v; } };
  const cls = (el, name, on) => {
    const k = '_c_' + name;
    on = !!on;
    if (el[k] !== on) { el[k] = on; el.classList.toggle(name, on); }
  };
  const sty = (el, prop, v) => { const k = '_s_' + prop; if (el[k] !== v) { el[k] = v; el.style[prop] = v; } };
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

  function ramp(stops) {
    return (v) => {
      if (v <= stops[0][0]) return 'rgb(' + stops[0][1] + ')';
      for (let i = 1; i < stops.length; i++) {
        if (v <= stops[i][0]) {
          const [a, ca] = stops[i - 1], [b, cb] = stops[i];
          const f = (v - a) / (b - a);
          return 'rgb(' + ca.map((c, j) => Math.round(c + (cb[j] - c) * f)) + ')';
        }
      }
      return 'rgb(' + stops[stops.length - 1][1] + ')';
    };
  }
  const BLUE = [77, 163, 255], CYAN = [45, 226, 230], GREEN = [61, 220, 132];
  const YELLOW = [255, 210, 63], RED = [255, 77, 90];
  const tyreColor = ramp([[55, BLUE], [78, CYAN], [90, GREEN], [104, GREEN], [112, YELLOW], [124, RED]]);
  const brakeColor = ramp([[150, BLUE], [350, GREEN], [800, GREEN], [950, YELLOW], [1100, RED]]);
  const wearColor = ramp([[0, GREEN], [40, GREEN], [60, YELLOW], [80, RED]]);
  const dmgColor = ramp([[1, YELLOW], [55, RED]]);

  function fmtLap(ms) {
    if (!ms || ms <= 0) return '–:––.–––';
    const m = Math.floor(ms / 60000), s = (ms % 60000) / 1000;
    return m + ':' + (s < 10 ? '0' : '') + s.toFixed(3);
  }
  function fmtSector(ms) {
    if (!ms || ms <= 0) return '—';
    return ms >= 60000 ? fmtLap(ms) : (ms / 1000).toFixed(3);
  }
  function fmtGap(ms) {
    if (!ms || ms <= 0) return '—';
    return ms >= 60000 ? '+' + fmtLap(ms).slice(0, -2) : '+' + (ms / 1000).toFixed(3);
  }
  function fmtClock(sec) {
    const m = Math.floor(sec / 60), s = sec % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  // ------------------------------------------------------------ montagem
  // Layout pela tela: monitor em pe (1080x1920), monitor/tablet deitado (1920x1080)
  // ou celular (compacto, letras grandes). Forcar: ?modo=celular ou ?modo=monitor na URL.
  const MODO = new URLSearchParams(location.search).get('modo');
  let fitKey = '';
  function fit() {
    const w = innerWidth, h = innerHeight;
    const deitado = w > h * 1.05;
    const celular = MODO === 'celular' || (MODO !== 'monitor' && Math.min(w, h) < 520);
    const key = w + 'x' + h + deitado + celular;
    if (key === fitKey) return;
    fitKey = key;
    document.body.classList.toggle('landscape', deitado);
    document.body.classList.toggle('phone', celular);
    const [W, H] = celular ? (deitado ? [1000, 460] : [460, 1000]) : (deitado ? [1920, 1080] : [1080, 1920]);
    const s = Math.min(w / W, h / H);
    stage.style.transform = 'translate(-50%, -50%) scale(' + s + ')';
  }
  // celular: tocar na barra de cima liga/desliga a tela cheia
  $('top').addEventListener('click', () => {
    if (!document.body.classList.contains('phone')) return;
    const el = document.documentElement;
    if (!document.fullscreenElement && el.requestFullscreen) el.requestFullscreen().catch(() => {});
    else if (document.exitFullscreen) document.exitFullscreen().catch(() => {});
  });
  addEventListener('resize', fit);
  fit();

  const leds = [];
  for (let i = 0; i < 15; i++) {
    const el = document.createElement('i');
    el.className = i < 5 ? 'g' : i < 10 ? 'r' : 'p';
    $('leds').appendChild(el);
    leds.push(el);
  }

  // Ordem das rodas no jogo: [TE, TD, DE, DD]
  const WHEELS = [
    { k: 'fl', i: 2, name: T('DIANT. ESQ.') }, { k: 'fr', i: 3, name: T('DIANT. DIR.') },
    { k: 'rl', i: 0, name: T('TRAS. ESQ.') }, { k: 'rr', i: 1, name: T('TRAS. DIR.') },
  ];
  for (const w of WHEELS) {
    const card = $('t_' + w.k);
    card.innerHTML =
      '<div class="t-head"><span class="lbl">' + w.name + '</span><span class="t-wear"><b data-r="wear">0</b>%</span></div>' +
      '<div class="t-temp" data-r="surf">–<small>°</small></div>' +
      '<div class="t-wearbar"><i data-r="wearBar"></i></div>' +
      '<div class="t-rows">' +
      '<div><span class="lbl">' + T('INTERNA') + '</span><b data-r="inner">–</b></div>' +
      '<div><span class="lbl">' + T('PRESSÃO') + '</span><b data-r="psi">–</b></div>' +
      '<div><span class="lbl">' + T('FREIO') + '</span><b data-r="brake">–</b></div></div>';
    w.card = card;
    w.wheel = $('w_' + w.k);
    for (const el of card.querySelectorAll('[data-r]')) w[el.dataset.r] = el;
  }

  const sectorEls = [];
  for (let i = 0; i < 3; i++) {
    const el = document.createElement('div');
    el.className = 'sec';
    el.innerHTML = '<span class="lbl">S' + (i + 1) + '</span><span class="v">—</span>';
    $('sectors').appendChild(el);
    sectorEls.push({ el, v: el.querySelector('.v') });
  }

  const stat = {};
  for (const [id, label] of [['last', T('ÚLTIMA')], ['best', T('MELHOR')], ['front', T('À FRENTE')],
    ['leader', T('LÍDER')], ['pen', T('PUNIÇÕES')], ['warns', T('AVISOS')]]) {
    const el = document.createElement('div');
    el.className = 'stat';
    el.innerHTML = '<span class="lbl">' + label + '</span><span class="v">—</span>';
    $('stats').appendChild(el);
    stat[id] = el.querySelector('.v');
  }

  const DMG = [['fwL', T('Asa diant. E'), ['d_fwL']], ['fwR', T('Asa diant. D'), ['d_fwR']],
    ['rearWing', T('Asa traseira'), ['d_rw']], ['floor', T('Assoalho'), ['d_floor']],
    ['diffuser', T('Difusor'), ['d_diffuser']], ['sidepod', 'Sidepods', ['d_spL', 'd_spR']],
    ['gearbox', T('Câmbio'), ['d_gearbox']], ['engine', T('Motor'), ['d_engine']]];
  for (const d of DMG) {
    const el = document.createElement('div');
    el.innerHTML = '<span>' + d[1] + '</span><b>OK</b>';
    $('dgrid').appendChild(el);
    d.val = el.querySelector('b');
    d.parts = d[2].map($);
  }

  const PU = [['ice', 'ICE'], ['tc', 'TURBO'], ['mguh', 'MGU-H'], ['mguk', 'MGU-K'], ['es', 'ES'], ['ce', 'CE']];
  for (const p of PU) {
    const el = document.createElement('div');
    el.innerHTML = '<span>' + p[1] + '</span><div class="bar"><i></i></div><b>0%</b>';
    $('pu').appendChild(el);
    p.bar = el.querySelector('i');
    p.val = el.querySelector('b');
  }

  const chip = {};
  for (const [id, label] of [['bias', 'BIAS'], ['diff', T('DIF.')], ['tc', 'TC'], ['abs', 'ABS'],
    ['engine', T('MOTOR')], ['window', T('JANELA PIT')], ['drsFault', T('FALHA DRS')], ['ersFault', T('FALHA ERS')],
    ['blown', T('MOTOR QUEBRADO')]]) {
    const el = document.createElement('div');
    el.className = 'chip';
    el.innerHTML = label + ' <b></b>';
    $('chips').appendChild(el);
    chip[id] = { el, v: el.querySelector('b') };
  }

  let tickMax = 0;
  function buildTicks(max) {
    if (max === tickMax) return;
    tickMax = max;
    const NS = 'http://www.w3.org/2000/svg';
    const g = $('ticks');
    g.textContent = '';
    for (let k = 0; k * 1000 <= max; k++) {
      const a = (135 + 270 * (k * 1000 / max)) * Math.PI / 180;
      const c = Math.cos(a), s = Math.sin(a);
      const line = document.createElementNS(NS, 'line');
      line.setAttribute('x1', 350 + 206 * c); line.setAttribute('y1', 285 + 206 * s);
      line.setAttribute('x2', 350 + 193 * c); line.setAttribute('y2', 285 + 193 * s);
      g.appendChild(line);
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', 350 + 170 * c); t.setAttribute('y', 285 + 170 * s);
      t.textContent = k;
      g.appendChild(t);
    }
    const red = Math.round(1000 * (1 - 1000 / max));   // ultimos 1000 rpm
    sty($('arcRed'), 'strokeDasharray', (1000 - red) + ' 1000');
    sty($('arcRed'), 'strokeDashoffset', String(-red));
  }
  buildTicks(13000);

  // ------------------------------------------------------------ desenho
  const E = {};
  for (const id of ['top', 'track', 'sessionType', 'flag', 'pos', 'lapLbl', 'lapNum', 'lapTotal', 'weather',
    'rain', 'trackTemp', 'airTemp', 'conn', 'leds', 'cluster', 'brakeBar', 'brakeVal', 'throttleBar',
    'throttleVal', 'arcVal', 'arcGlow', 'rpmTxt', 'gear', 'suggested', 'speed', 'lights', 'toast', 'gDot', 'gLat',
    'gLong', 'steerDot', 'clutchBar', 'drsBadge', 'drsTxt', 'drsSub', 'otBadge', 'otSub', 'pitBadge',
    'pitSub', 'invalid', 'pitInfo', 'curLap', 'delta', 'ersMode', 'ersPct', 'ersBar', 'ersHarvBar',
    'ersHarv', 'ersDepBar', 'ersDep', 'fuelMix', 'fuelLaps', 'fuelKg', 'fuelBar', 'fuelPct', 'powerBar',
    'power', 'compound', 'compoundTxt', 'warn', 'wait', 'waitMsg']) E[id] = $(id);
  const lightEls = [...E.lights.children];
  let waitHidden = false;   // "Ver o painel": esconde a tela de espera mesmo sem telemetria

  const FUEL_MIX = [T('POBRE'), T('PADRÃO'), T('RICA'), T('MÁXIMA')];
  const ERS_MODE = [T('NENHUM'), T('MÉDIO'), 'HOTLAP', 'OVERTAKE'];
  const VISUAL = { 16: ['S', '#ff4d5a', T('Macio')], 17: ['M', '#ffd23f', T('Médio')], 18: ['H', '#eaf0f8', T('Duro')],
    7: ['I', '#3ddc84', T('Intermediário')], 8: ['W', '#4da3ff', T('Chuva')] };
  const ACTUAL = { 16: 'C5', 17: 'C4', 18: 'C3', 19: 'C2', 20: 'C1', 21: 'C0', 22: 'C6' };
  const GEAR = (g) => (g === 0 ? 'N' : g < 0 ? 'R' : String(g));

  const T0 = { speed: 0, throttle: 0, steer: 0, brake: 0, clutch: 0, gear: 0, rpm: 0, drs: 0, revPct: 0,
    revBits: 0, brakeTemp: [0, 0, 0, 0], tyreSurf: [0, 0, 0, 0], tyreInner: [0, 0, 0, 0], engineTemp: 0,
    pressure: [0, 0, 0, 0], suggested: 0 };
  const ST0 = { tc: 0, abs: 0, fuelMix: 1, brakeBias: 0, pitLimiter: 0, fuel: 0, fuelCap: 0, fuelLaps: 0,
    maxRpm: 13000, idleRpm: 0, drsAllowed: 0, drsDist: 0, compound: 0, visual: 0, tyreAge: 0, flag: 0,
    powerKw: 0, ersStore: 0, ersMode: 0, ersHarv: 0, ersDeployed: 0, ersLimit: null };
  const D0 = { wear: [0, 0, 0, 0] };

  function render(S) {
    const t = S.tel || T0, st = S.status || ST0, d = S.damage || D0;
    const lap = S.lap, ses = S.session, t2 = S.t2;
    const regs26 = !!(t2 && t2.regs2026);

    // conexao e avisos
    cls(E.wait, 'show', !S.connected && !waitHidden);
    txt(E.waitMsg, T('Nenhuma telemetria chegando. No jogo, abra:'));
    txt(E.conn, !S.connected ? T('SEM SINAL') : S.demo ? 'DEMO' : T('AO VIVO · UDP ') + S.format);
    cls(E.conn, 'live', S.connected && !S.demo);
    cls(E.conn, 'demo', S.connected && S.demo);
    txt(E.warn, S.warn || '');

    // topo
    txt(E.track, ses ? ses.track : '—');
    txt(E.sessionType, ses ? ses.type : T('Sem sessão'));
    txt(E.weather, ses ? ses.weather : '—');
    txt(E.trackTemp, ses ? String(ses.trackTemp) : '–');
    txt(E.airTemp, ses ? String(ses.airTemp) : '–');
    let rain = '';
    if (ses && ses.rain.length) {
      rain = T(' · chuva ') + ses.rain[0][1] + '%';
      const later = ses.rain.find((r) => r[0] > 0 && r[1] !== ses.rain[0][1]);
      if (later) rain += ' → ' + later[1] + T('% em ') + later[0] + ' min';
    }
    txt(E.rain, rain);
    txt(E.pos, lap && lap.pos ? String(lap.pos) : '–');
    txt(E.lapNum, lap && lap.num ? String(lap.num) : '–');
    txt(E.lapTotal, ses && ses.isRace && ses.totalLaps ? '/' + ses.totalLaps
      : ses && ses.timeLeft ? ' ' + fmtClock(ses.timeLeft) : '');

    let flag = '', fcls = '', pill = '';
    const sc = ses ? ses.safetyCar : 0;
    if (sc === 1) { flag = 'SAFETY CAR'; fcls = 'f-yellow'; }
    else if (sc === 2) { flag = 'VSC'; fcls = 'f-yellow'; }
    else if (sc === 3) { flag = T('VOLTA DE FORMAÇÃO'); }
    else if (st.flag === 3) { flag = T('BANDEIRA AMARELA'); fcls = 'f-yellow'; }
    else if (st.flag === 2) { flag = T('BANDEIRA AZUL'); fcls = 'f-blue'; pill = 'blue'; }
    else if (st.flag === 1) { flag = T('BANDEIRA VERDE'); fcls = 'f-green'; pill = 'green'; }
    txt(E.flag, flag);
    cls(E.flag, 'blue', pill === 'blue');
    cls(E.flag, 'green', pill === 'green');
    for (const c of ['f-yellow', 'f-blue', 'f-green']) cls(E.top, c, fcls === c);

    // LEDs de giro
    let bits = t.revBits;
    if (!bits && t.revPct > 0) bits = (1 << Math.round(t.revPct * 15 / 100)) - 1;
    for (let i = 0; i < 15; i++) cls(leds[i], 'on', bits & (1 << i));
    const shift = t.revPct >= 97;
    cls(E.leds, 'shift', shift);
    cls(E.cluster, 'shift', shift);
    cls(E.cluster, 'pit', st.pitLimiter);

    // cluster
    const maxRpm = st.maxRpm > 5000 ? st.maxRpm : 13000;
    buildTicks(maxRpm);
    const dash = (clamp(t.rpm / maxRpm, 0, 1) * 1000).toFixed(1) + ' 1000';
    sty(E.arcVal, 'strokeDasharray', dash);
    sty(E.arcGlow, 'strokeDasharray', dash);
    txt(E.rpmTxt, t.rpm.toLocaleString(LOCALE));
    txt(E.gear, GEAR(t.gear));
    txt(E.speed, String(t.speed));
    txt(E.suggested, t.suggested > 0 && t.suggested !== t.gear ? '▸ ' + t.suggested : '');
    sty(E.throttleBar, 'transform', 'scaleY(' + t.throttle.toFixed(3) + ')');
    sty(E.brakeBar, 'transform', 'scaleY(' + t.brake.toFixed(3) + ')');
    txt(E.throttleVal, String(Math.round(t.throttle * 100)));
    txt(E.brakeVal, String(Math.round(t.brake * 100)));

    // volante, embreagem, forca G
    sty(E.steerDot, 'transform', 'translateX(' + (clamp(t.steer, -1, 1) * 150).toFixed(1) + 'px)');
    sty(E.clutchBar, 'transform', 'scaleX(' + (t.clutch / 100).toFixed(2) + ')');
    const m = S.motion || { gLat: 0, gLong: 0 };
    const k = 32 / 5;   // 5 G = borda do circulo
    sty(E.gDot, 'transform', 'translate(' + (clamp(m.gLat, -5.5, 5.5) * k).toFixed(1) + 'px,' +
      (clamp(m.gLong, -5.5, 5.5) * k).toFixed(1) + 'px)');
    txt(E.gLat, Math.abs(m.gLat).toFixed(1));
    txt(E.gLong, (m.gLong < -0.05 ? '−' : '') + Math.abs(m.gLong).toFixed(1));

    // DRS / aero ativa / overtake / pit
    let dActive, dAvail, dDist;
    if (regs26) {
      txt(E.drsTxt, 'AERO');
      dActive = t2.aeroMode === 1; dAvail = t2.aeroAvail === 1; dDist = t2.aeroDist;
    } else {
      txt(E.drsTxt, 'DRS');
      dActive = t.drs === 1; dAvail = st.drsAllowed === 1; dDist = st.drsDist;
    }
    const drsFault = !!d.drsFault && !regs26;
    cls(E.drsBadge, 'active', dActive && !drsFault);
    cls(E.drsBadge, 'avail', dAvail && !dActive && !drsFault);
    cls(E.drsBadge, 'fault', drsFault);
    txt(E.drsSub, drsFault ? T('FALHA') : dActive ? (regs26 ? T('MODO RETA') : T('ABERTO')) : dAvail ? T('DISPONÍVEL')
      : dDist > 0 ? T('em ') + dDist + ' m' : '');
    cls(E.otBadge, 'show', regs26);
    if (regs26) {
      cls(E.otBadge, 'active', t2.otActive === 1);
      cls(E.otBadge, 'avail', t2.otAvail === 1 && !t2.otActive);
      txt(E.otSub, t2.otActive ? T('ATIVO') : t2.otAvail ? T('DISPONÍVEL') : t2.otDist > 0 ? T('em ') + t2.otDist + ' m' : '');
    }
    cls(E.pitBadge, 'warnon', st.pitLimiter);
    txt(E.pitSub, st.pitLimiter && ses && ses.pitLimit ? ses.pitLimit + ' km/h' : T('LIMITADOR'));

    // tempos
    txt(E.curLap, fmtLap(lap ? lap.cur : 0));
    cls(E.curLap, 'invalid', lap && lap.invalid);
    cls(E.invalid, 'on', lap && lap.invalid);
    let pit = '';
    if (lap && lap.pitStatus) {
      pit = lap.pitStatus === 1 ? 'PIT LANE' : T('NOS BOXES');
      if (lap.pitLaneMs) pit += ' ' + (lap.pitLaneMs / 1000).toFixed(1) + 's';
    }
    txt(E.pitInfo, pit);
    const dl = lap ? lap.delta : null;
    txt(E.delta, dl == null ? '—' : (dl < 0 ? '−' : '+') + (Math.abs(dl) / 1000).toFixed(3));
    cls(E.delta, 'neg', dl != null && dl < 0);
    cls(E.delta, 'pos', dl != null && dl > 0);
    for (let i = 0; i < 3; i++) {
      const s = lap && lap.sectors[i], se = sectorEls[i];
      txt(se.v, s ? fmtSector(s.t) : '—');
      for (const c of ['y', 'g', 'p']) cls(se.el, c, s && s.c === c);
      cls(se.el, 'stale', s && s.stale);
      cls(se.el, 'active', lap && lap.sector === i && lap.driverStatus !== 0);
    }
    txt(stat.last, fmtLap(lap ? lap.last : 0));
    txt(stat.best, fmtLap(lap ? lap.best : 0));
    cls(stat.best, 'p', lap && lap.bestOverall);
    txt(stat.front, lap ? fmtGap(lap.gapFront) : '—');
    txt(stat.leader, lap ? fmtGap(lap.gapLeader) : '—');
    let pen = '—';
    if (lap) {
      const parts = [];
      if (lap.penalties) parts.push(lap.penalties + 's');
      if (lap.dt) parts.push(lap.dt + ' DT');
      if (lap.sg) parts.push(lap.sg + ' SG');
      if (parts.length) pen = parts.join(' ');
    }
    txt(stat.pen, pen);
    cls(stat.pen, 'bad', pen !== '—');
    txt(stat.warns, lap ? String(lap.warnings) : '—');

    // ERS
    const ersFrac = clamp(st.ersStore / 4e6, 0, 1);
    html(E.ersPct, Math.round(ersFrac * 100) + '<small>%</small>');
    sty(E.ersBar, 'transform', 'scaleX(' + ersFrac.toFixed(3) + ')');
    cls(E.ersBar.parentNode, 'low', ersFrac < 0.15);
    const modes = S.format >= 2026 ? [T('NENHUM'), T('MÉDIO'), 'HOTLAP', 'BOOST'] : ERS_MODE;
    txt(E.ersMode, modes[st.ersMode] || '—');
    cls(E.ersMode, 'hot', st.ersMode === 3);
    const harvMax = st.ersLimit || 4e6;
    sty(E.ersHarvBar, 'transform', 'scaleX(' + clamp(st.ersHarv / harvMax, 0, 1).toFixed(3) + ')');
    txt(E.ersHarv, (st.ersHarv / 1e6).toFixed(2) + ' MJ');
    sty(E.ersDepBar, 'transform', 'scaleX(' + clamp(st.ersDeployed / harvMax, 0, 1).toFixed(3) + ')');
    txt(E.ersDep, (st.ersDeployed / 1e6).toFixed(2) + ' MJ');

    // combustivel
    txt(E.fuelLaps, (st.fuelLaps < 0 ? '−' : '+') + Math.abs(st.fuelLaps).toFixed(2));
    cls(E.fuelLaps, 'neg', st.fuelLaps < 0);
    cls(E.fuelLaps, 'pos', st.fuelLaps >= 0 && !!S.status);
    html(E.fuelKg, st.fuel.toFixed(1) + '<small> kg</small>');
    const fuelFrac = st.fuelCap > 0 ? clamp(st.fuel / st.fuelCap, 0, 1) : 0;
    sty(E.fuelBar, 'transform', 'scaleX(' + fuelFrac.toFixed(3) + ')');
    txt(E.fuelPct, Math.round(fuelFrac * 100) + '%');
    txt(E.fuelMix, FUEL_MIX[st.fuelMix] || '—');
    sty(E.powerBar, 'transform', 'scaleX(' + clamp(st.powerKw / 760, 0, 1).toFixed(3) + ')');
    txt(E.power, Math.round(st.powerKw) + ' kW');

    // pneus e freios
    const vis = VISUAL[st.visual];
    txt(E.compound, vis ? vis[0] : '–');
    sty(E.compound, 'borderColor', vis ? vis[1] : '');
    txt(E.compoundTxt, vis ? vis[2] + (ACTUAL[st.compound] ? ' ' + ACTUAL[st.compound] : '') + ' · ' +
      st.tyreAge + (st.tyreAge === 1 ? T(' volta') : T(' voltas')) : '—');
    for (const w of WHEELS) {
      const surf = t.tyreSurf[w.i], col = S.tel ? tyreColor(surf) : '';
      html(w.surf, (S.tel ? surf : '–') + '<small>°</small>');
      sty(w.surf, 'color', col);
      sty(w.card, 'borderTopColor', col);
      sty(w.wheel, 'fill', col);
      txt(w.inner, S.tel ? t.tyreInner[w.i] + '°' : '–');
      txt(w.psi, S.tel ? t.pressure[w.i].toFixed(1) + ' psi' : '–');
      txt(w.brake, S.tel ? t.brakeTemp[w.i] + '°' : '–');
      sty(w.brake, 'color', S.tel ? brakeColor(t.brakeTemp[w.i]) : '');
      const wear = d.wear[w.i];
      txt(w.wear, String(Math.round(wear)));
      sty(w.wearBar, 'transform', 'scaleX(' + clamp(1 - wear / 100, 0, 1).toFixed(3) + ')');
      sty(w.wearBar, 'background', wearColor(wear));
    }

    // danos
    for (const x of DMG) {
      const v = d[x[0]] || 0, col = v > 0 ? dmgColor(v) : '';
      txt(x.val, v > 0 ? v + '%' : 'OK');
      sty(x.val, 'color', col);
      for (const p of x.parts) sty(p, 'fill', col);
    }
    for (const p of PU) {
      const v = d[p[0]] || 0;
      txt(p.val, v + '%');
      sty(p.bar, 'transform', 'scaleX(' + (v / 100).toFixed(2) + ')');
      sty(p.bar, 'background', wearColor(v));
    }

    // ajustes e falhas
    const setChip = (id, value, show, bad) => {
      cls(chip[id].el, 'hidden', !show);
      cls(chip[id].el, 'bad', bad);
      txt(chip[id].v, value);
    };
    setChip('bias', st.brakeBias + '%', true);
    setChip('diff', S.setup ? S.setup.diffOn + '%' : '–', !!S.setup);
    setChip('tc', ['OFF', T('MÉDIO'), 'TOTAL'][st.tc] || '–', true);
    setChip('abs', st.abs ? 'ON' : 'OFF', true);
    setChip('engine', t.engineTemp + '°', true, t.engineTemp >= 125);
    setChip('window', ses ? ses.pitIdeal + '–' + ses.pitLatest : '', !!(ses && ses.isRace && ses.pitIdeal), false);
    setChip('drsFault', '', !!d.drsFault, true);
    setChip('ersFault', '', !!d.ersFault, true);
    setChip('blown', '', !!(d.blown || d.seized), true);

    handleEvent(S.event);
    handleCoach(S.coach);
  }

  // ------------------------------------------------------------ radio do engenheiro
  const R = { box: $('radio'), msg: $('radioMsg'), mode: $('voiceMode'), corners: $('rCorners'),
    age: $('radioAge'), an: $('analysis'), aSub: $('aSub'), aRows: $('aRows'), aMap: $('aMap'),
    aLog: $('aLog') };
  const MODES = [['tudo', T('VOZ: TUDO')], ['importante', T('VOZ: SÓ IMPORTANTE')], ['mudo', T('VOZ: DESLIGADA')]];
  const synth = window.speechSynthesis;
  let mode = 'tudo';
  try { mode = localStorage.getItem('painel.voz') || 'tudo'; } catch (e) { /* sem storage */ }
  function setMode(m) {
    mode = MODES.some((x) => x[0] === m) ? m : 'tudo';
    try { localStorage.setItem('painel.voz', mode); } catch (e) { /* sem storage */ }
    txt(R.mode, MODES.find((x) => x[0] === mode)[1]);
    cls(R.mode, 'off', mode === 'mudo');
    cls(R.mode, 'imp', mode === 'importante');
    if (mode === 'mudo') {
      pararFala();
      queue.length = 0;
    }
  }
  function cycleMode() {
    const i = MODES.findIndex((x) => x[0] === mode);
    setMode(MODES[(i + 1) % MODES.length][0]);
  }

  let voice = null, blocked = false, speaking = false, talkOk = true;
  // ate quando a fala atual deve durar (ms do performance.now) e o numero da fala atual:
  // uma fala nova sempre corta a anterior, e uma resposta atrasada do servidor e descartada
  let falaAte = 0, falaId = 0;
  function pickVoice() {
    const vs = synth ? synth.getVoices() : [];
    voice = LANG_EN
      ? vs.find((v) => /en[-_]GB/i.test(v.lang)) || vs.find((v) => /^en/i.test(v.lang)) || null
      : vs.find((v) => /pt[-_]BR/i.test(v.lang) && /Maria|Francisca|Thalita|Daniel/i.test(v.name)) ||
        vs.find((v) => /pt[-_]BR/i.test(v.lang)) || vs.find((v) => /^pt/i.test(v.lang)) || null;
  }
  if (synth) { pickVoice(); synth.onvoiceschanged = pickVoice; synth.cancel(); }

  let neural = false, volume = 1, radioFx = true, chiado = 0.35, audio = null, fimFala = null, chiadoSrc = null;
  function falando(on, duracaoMs) {
    speaking = on;
    if (on) falaAte = performance.now() + (duracaoMs || 15000);
    cls(R.box, 'talking', on);
  }
  function bloqueado() {
    blocked = true;
    txt(R.msg, T('Clique aqui (ou em qualquer lugar do painel) para ativar a voz do engenheiro.'));
    cls(R.msg, 'blocked', true);
  }

  // ---- som de radio de equipe (Web Audio)
  let actx = null, ruido = null;
  function audioCtx() {
    if (!actx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      actx = new AC();
    }
    if (actx.state === 'suspended') actx.resume().catch(() => {});
    return actx;
  }
  function curva(k) {
    const n = 1024, a = new Float32Array(n);
    for (let i = 0; i < n; i++) { const x = i * 2 / n - 1; a[i] = (1 + k) * x / (1 + k * Math.abs(x)); }
    return a;
  }
  // saida: volume geral; com efeito, a voz passa por filtro de banda estreita + leve saturacao + compressor
  function cadeia(c, fx) {
    const out = c.createGain();
    out.gain.value = volume;
    out.connect(c.destination);
    if (!fx) return { entrada: out, out };
    const hp = c.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 380; hp.Q.value = 0.8;
    const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 3200; lp.Q.value = 1;
    const pk = c.createBiquadFilter(); pk.type = 'peaking'; pk.frequency.value = 1900; pk.Q.value = 1.1; pk.gain.value = 6;
    const sat = c.createWaveShaper(); sat.curve = curva(6); sat.oversample = '2x';
    const comp = c.createDynamicsCompressor();
    comp.threshold.value = -26; comp.ratio.value = 8; comp.attack.value = 0.002; comp.release.value = 0.12;
    const ganho = c.createGain(); ganho.gain.value = 1.4;
    hp.connect(lp); lp.connect(pk); pk.connect(sat); sat.connect(comp); comp.connect(ganho); ganho.connect(out);
    return { entrada: hp, out };
  }
  function bip(c, dest, t, freq, dur, vol) {
    const o = c.createOscillator(), g = c.createGain();
    o.type = 'sine';
    o.frequency.value = freq;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(vol, t + 0.006);
    g.gain.setValueAtTime(vol, t + dur - 0.012);
    g.gain.linearRampToValueAtTime(0, t + dur);
    o.connect(g); g.connect(dest);
    o.start(t); o.stop(t + dur + 0.02);
  }
  function estatica(c, dest, t0, t1, nivel) {
    if (nivel <= 0) return null;
    if (!ruido) {
      ruido = c.createBuffer(1, c.sampleRate * 2, c.sampleRate);
      const d = ruido.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    const s = c.createBufferSource(), bp = c.createBiquadFilter(), g = c.createGain();
    s.buffer = ruido; s.loop = true;
    bp.type = 'bandpass'; bp.frequency.value = 2600; bp.Q.value = 0.7;
    const v = 0.06 * nivel;
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(v, t0 + 0.04);
    g.gain.setValueAtTime(v, Math.max(t0 + 0.05, t1 - 0.06));
    g.gain.linearRampToValueAtTime(0, t1);
    s.connect(bp); bp.connect(g); g.connect(dest);
    s.start(t0); s.stop(t1 + 0.05);
    return s;
  }
  // "clique" quando voce aperta o botao do radio no volante
  function clique() {
    const c = audioCtx();
    if (!c || c.state !== 'running') return;
    const { out } = cadeia(c, false);
    bip(c, out, c.currentTime + 0.01, 1350, 0.05, 0.16);
  }
  function abreRadio(c, out, t) { bip(c, out, t, 1150, 0.075, 0.2); }
  function fechaRadio(c, out, t) { bip(c, out, t, 1150, 0.05, 0.18); bip(c, out, t + 0.07, 860, 0.08, 0.18); }

  function pararFala() {
    falaId++;
    if (synth) synth.cancel();
    if (audio) { try { audio.stop(); } catch (e) { /* ja parou */ } audio = null; }
    if (chiadoSrc) { try { chiadoSrc.stop(); } catch (e) { /* ja parou */ } chiadoSrc = null; }
    clearTimeout(fimFala);
    falando(false);
  }

  // voz do Windows (sem internet ou se a natural falhar): bipes de radio, sem filtro
  function speakWindows(text, id) {
    if (!synth) return;
    if (id === undefined) { pararFala(); id = falaId; }
    const c = radioFx ? audioCtx() : null;
    const ok = c && c.state === 'running';
    const u = new SpeechSynthesisUtterance(text);
    if (voice) u.voice = voice;
    u.lang = LOCALE;
    u.rate = 1.12;
    u.volume = volume;
    falando(true, 2500 + text.length * 95);   // a voz do Windows nao diz a duracao: estimativa pelo tamanho
    if (ok) { const { out } = cadeia(c, false); abreRadio(c, out, c.currentTime + 0.01); }
    u.onend = () => {
      if (id !== falaId) return;
      if (ok) { const { out } = cadeia(c, false); fechaRadio(c, out, c.currentTime + 0.02); }
      falando(false);
    };
    u.onerror = (e) => { if (id !== falaId) return; falando(false); if (e.error === 'not-allowed') bloqueado(); };
    setTimeout(() => { if (id === falaId) synth.speak(u); }, ok ? 140 : 0);
  }

  // voz natural: o servidor ja deixou o audio pronto quando a mensagem foi criada
  async function speak(text, tom) {
    pararFala();                 // nunca duas vozes: a fala nova corta a que estiver tocando
    const id = falaId;
    if (!neural) return speakWindows(text, id);
    const c = audioCtx();
    if (!c) return speakWindows(text, id);
    falando(true, 12000);        // o servidor pode levar alguns segundos para gerar o audio
    let buf;
    try {
      const r = await fetch('/tts?tom=' + encodeURIComponent(tom || 'normal') + '&t=' + encodeURIComponent(text));
      if (!r.ok) throw new Error('sem voz natural');
      buf = await c.decodeAudioData(await r.arrayBuffer());
    } catch (e) {
      if (id !== falaId) return;
      falando(false);
      return speakWindows(text, id);
    }
    if (id !== falaId) return;   // outra fala comecou enquanto este audio chegava
    if (c.state !== 'running') { falando(false); bloqueado(); return; }
    const { entrada, out } = cadeia(c, radioFx);
    const t0 = c.currentTime + 0.03;
    const inicio = t0 + (radioFx ? 0.17 : 0);
    const fim = inicio + buf.duration;
    if (radioFx) {
      abreRadio(c, out, t0);
      chiadoSrc = estatica(c, out, t0 + 0.06, fim + 0.08, chiado);
      fechaRadio(c, out, fim + 0.06);
    }
    const src = c.createBufferSource();
    src.buffer = buf;
    src.connect(entrada);
    src.start(inicio);
    audio = src;
    const dur = (fim - c.currentTime + (radioFx ? 0.3 : 0.05)) * 1000;
    falaAte = performance.now() + dur;   // agora a duracao e conhecida: a fila espera o audio inteiro
    clearTimeout(fimFala);
    fimFala = setTimeout(() => { if (id !== falaId) return; audio = null; falando(false); }, dur);
  }
  addEventListener('pointerdown', () => {
    if (actx && actx.state === 'suspended') actx.resume().catch(() => {});
    if (!blocked) return;
    blocked = false;
    cls(R.msg, 'blocked', false);
    speak(T('Rádio ativado.'), 'normal');
  });

  // ---- perguntar pela voz (UDP Action 11, tecla M ou 🎤): o navegador transcreve e o servidor entende
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const NATIVO = !!window.__TAURI__;              // dentro do app nativo quem ouve e o app (Windows)
  const micOk = NATIVO || (!!SR && window.isSecureContext);   // no celular pela rede (http) o navegador nao deixa
  const micBtn = $('micBtn');
  let ouvindo = false, rec = null, recTimer = null;
  cls(micBtn, 'sem', !micOk);
  function avisoRadio(t) { txt(R.msg, t); cls(R.msg, 'p1', false); }
  function fimOuvir() {
    ouvindo = false;
    clearTimeout(recTimer);
    cls(R.box, 'ouvindo', false);
    cls(micBtn, 'on', false);
    const c = actx;
    if (c && c.state === 'running') { const { out } = cadeia(c, false); fechaRadio(c, out, c.currentTime + 0.01); }
  }
  // no app nativo: o app grava o microfone e transcreve com o Whisper, offline (o WebView2 nao tem o
  // reconhecimento do Chrome)
  const ERROS_OUVIR = {
    nada: () => T('Não ouvi nada. Aperte e fale de novo.'),
    microfone: () => T('Não consegui usar o microfone. Confira se ele está conectado e liberado para apps em Privacidade > Microfone.'),
    modelo: () => T('Não consegui baixar o modelo de voz. Confira a internet e tente de novo.'),
  };
  const FASES_OUVIR = { ouvindo: () => '🎤 ' + T('Ouvindo…'), entendendo: () => '🎤 ' + T('Entendendo…') };
  async function ouvirNativo() {
    const inv = window.__TAURI__.core.invoke;
    if (ouvindo) { inv('parar_ouvir').catch(() => {}); return; }   // apertou de novo: para de ouvir
    pararFala();
    const c = audioCtx();
    if (c && c.state === 'running') { const { out } = cadeia(c, false); abreRadio(c, out, c.currentTime + 0.01); }
    ouvindo = true;
    cls(R.box, 'ouvindo', true);
    cls(micBtn, 'on', true);
    avisoRadio('🎤 ' + T('Ouvindo…'));
    let texto = null, erro = null;
    const acompanha = setInterval(async () => {   // baixando o modelo (1a vez), ouvindo, entendendo
      try {
        const e = await inv('estado_ouvido');
        if (e.fase === 'baixando') avisoRadio('⬇ ' + T('Baixando o modelo de voz (só na primeira vez): %d%').replace('%d', e.baixado));
        else if (FASES_OUVIR[e.fase]) avisoRadio(FASES_OUVIR[e.fase]());
      } catch (err) { /* segue */ }
    }, 300);
    try { texto = await inv('ouvir'); } catch (e) { erro = String(e); }
    clearInterval(acompanha);
    fimOuvir();
    if (texto) {
      avisoRadio('🎤 “' + texto + '”');
      fetch('/api/voz', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto }) }).catch(() => avisoRadio(T('O servidor do painel não respondeu.')));
      return;
    }
    const cod = (erro || '').split(':')[0];
    avisoRadio(ERROS_OUVIR[cod] ? ERROS_OUVIR[cod]() : T('Não consegui ouvir: ') + erro);
  }

  function ouvir() {
    if (NATIVO) return ouvirNativo();
    if (ouvindo) { if (rec) rec.stop(); return; }      // apertou de novo: para de ouvir
    if (!micOk) { avisoRadio(T('Reconhecimento de voz indisponível aqui. Use o Chrome ou o Edge no PC.')); return; }
    pararFala();                                         // ele para de falar para ouvir voce
    const c = audioCtx();
    if (c && c.state === 'running') { const { out } = cadeia(c, false); abreRadio(c, out, c.currentTime + 0.01); }
    ouvindo = true;
    cls(R.box, 'ouvindo', true);
    cls(micBtn, 'on', true);
    avisoRadio('🎤 ' + T('Ouvindo…'));
    let final = '';
    rec = new SR();
    rec.lang = LOCALE;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = false;                              // para sozinho quando voce fica em silencio
    rec.onresult = (e) => {
      let parcial = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
        else parcial += e.results[i][0].transcript;
      }
      avisoRadio('🎤 ' + (final + parcial || T('Ouvindo…')));
    };
    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') avisoRadio(T('Permita o microfone para falar com o engenheiro.'));
      else if (e.error === 'no-speech') avisoRadio(T('Não ouvi nada. Aperte e fale de novo.'));
      else if (e.error === 'network') avisoRadio(T('Sem internet para reconhecer a voz.'));
      else if (e.error === 'audio-capture') avisoRadio(T('Nenhum microfone encontrado.'));
    };
    rec.onend = () => {
      fimOuvir();
      const texto = final.trim();
      if (!texto) return;
      avisoRadio('🎤 “' + texto + '”');
      fetch('/api/voz', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto }) }).catch(() => avisoRadio(T('O servidor do painel não respondeu.')));
    };
    clearTimeout(recTimer);
    recTimer = setTimeout(() => { if (ouvindo && rec) rec.stop(); }, 9000);   // no maximo 9 s por pergunta
    try { rec.start(); } catch (e) { fimOuvir(); }
  }
  micBtn.addEventListener('click', (e) => { e.stopPropagation(); ouvir(); });

  const heard = new Set();
  const queue = [];
  const log = [];
  let primed = false, shown = null, reportKey = '', lastPtt = null, lastEscuta = null, lastCmd = null;

  function showMsg(m) {
    shown = m;
    if (blocked) return;
    txt(R.msg, m.show);
    cls(R.msg, 'p1', m.pri === 1);
    cls(R.box, 'p1', m.pri === 1);
  }

  function handleCoach(c) {
    if (!c) return;
    coach = c;
    const now = performance.now();
    if (TW.box.classList.contains('show') && now - twUltimo > 250) { twUltimo = now; renderTower(c.torre); }
    talkOk = c.talk;
    if (c.voice) {
      neural = c.voice.neural;
      volume = c.voice.volume / 100;
      radioFx = c.voice.radio !== false;
      chiado = (c.voice.chiado == null ? 35 : c.voice.chiado) / 100;
    }
    if (c.cmd && c.cmd.seq !== lastCmd) {   // comando do app nativo (tecla global ou controle)
      if (lastCmd !== null) {
        const a = c.cmd.acao;
        if (a === 'torre') toggleTower();
        else if (a === 'analise') toggleAnalysis();
        else if (a === 'ajustes') toggleCfg();
        else if (a === 'fechar') fecharTudo();
        else if (a === 'menu') toggleMenu();
      }
      lastCmd = c.cmd.seq;
    }
    if (c.escuta !== lastEscuta) {     // apertou o botao de voz no volante: abre o radio e ouve
      if (lastEscuta !== null && c.escuta != null) ouvir();
      lastEscuta = c.escuta;
    }
    if (c.ptt !== lastPtt) {           // apertou o botao do radio no volante
      if (lastPtt !== null && mode !== 'mudo') clique();
      lastPtt = c.ptt;
    }
    cls(R.box, 'quiet', !!c.silencio);
    for (const m of c.msgs) {
      if (heard.has(m.seq)) continue;
      heard.add(m.seq);
      const item = Object.assign({}, m, { rx: now - m.age });
      log.unshift(item.show);
      if (log.length > 10) log.pop();
      if (!primed) continue;       // ao abrir o painel, nao repete mensagens antigas
      queue.push(item);
      showMsg(item);
    }
    if (!primed) {
      primed = true;
      if (c.msgs.length) {
        const last = c.msgs[c.msgs.length - 1];
        showMsg(Object.assign({}, last, { rx: now - last.age }));
      }
    }
    const fl = c.live && c.live.flash;
    const fseq = fl ? fl.seq : 0;
    if (lastFlash === null) lastFlash = fseq;          // ao abrir o painel nao pisca o antigo
    else if (fseq !== lastFlash) { lastFlash = fseq; if (fl) mostraFlash(fl); }
    const p = c.pit;
    html(pitPrev, p ? T('PIT AGORA → ') + '<b>P' + p.pos + '</b>' + (p.frente ? T(' · atrás de ') + esc(p.frente[0]) +
      ' (' + DEC(p.frente[1]) + ' s)' : '') : '');
    const tr = c.treino || {};
    txt(treinoChip, tr.curva ? T('TREINO · C') + tr.curva : '');
    const key = (c.report ? c.report.lap + ':' + c.report.ms : '') + '|' + Object.keys(c.habits || {}).join(',') +
      '|' + (c.live ? c.live.lap + ':' + c.live.corners.length : '') + '|' + c.nCorners + '|' +
      (tr.curva || '') + (tr.metas || []).map((m) => m.prog + (m.feito ? '!' : '')).join(',') + '|' +
      (c.acerto ? c.acerto.voltas + ':' + c.acerto.achados.length + ':' + !!c.acerto.novo : '');
    if (key !== reportKey) {
      reportKey = key;
      renderCorners(c);
      renderAnalysis(c);
    }
    if (c.mapVer !== mapVer && R.an.classList.contains('show')) loadMap(c.mapVer);
  }

  function pump() {
    const now = performance.now();
    if (shown) txt(R.age, T('há %d s').replace('%d', Math.max(0, Math.round((now - shown.rx) / 1000))));
    // protecao se o navegador travar a fala: passou bem da duracao esperada, corta (em vez de falar por cima)
    if (speaking && now > falaAte + 3000) pararFala();
    for (let i = queue.length - 1; i >= 0; i--) {
      if (now - queue[i].rx > queue[i].ttl * 1000) queue.splice(i, 1);
    }
    if (speaking || blocked || ouvindo || !queue.length || mode === 'mudo') return;
    const ok = queue.filter((m) => mode === 'tudo' || m.pri <= 2);
    if (!ok.length) return;
    ok.sort((a, b) => a.pri - b.pri || a.rx - b.rx);
    const m = ok[0];
    const wait = now - m.rx;
    // fala nas retas; respostas aos botoes saem na hora; avisos importantes nao esperam muito
    if (talkOk || m.resp || (m.pri === 1 && wait > 2500) || (m.pri === 2 && wait > 8000)) {
      queue.splice(queue.indexOf(m), 1);
      speak(m.text, m.tom);
    }
  }

  function lossClass(l) {
    if (l == null) return '';
    if (l >= 0.15) return 'lbad';
    if (l >= 0.06) return 'lwarn';
    if (l <= -0.03) return 'lgood';
    return '';
  }
  const sgn = (x, d) => (x > 0 ? '+' : x < 0 ? '−' : '') + DEC(Math.abs(x).toFixed(d));

  // curvas no radio: as ja feitas nesta volta aparecem ao vivo; as outras mostram a volta anterior, apagadas
  function renderCorners(c) {
    const rep = c.report;
    const vivo = {};
    if (c.live && c.live.corners) for (const k of c.live.corners) vivo[k.n] = k.d;
    const temVivo = Object.keys(vivo).length > 0;
    if ((!rep || !rep.corners.length) && !temVivo) {
      html(R.corners, '<span class="empty">' + (c.nCorners ? c.nCorners + T(' CURVAS MAPEADAS · ANÁLISE APÓS A PRÓXIMA VOLTA')
        : T('AS CURVAS SÃO MAPEADAS NA PRIMEIRA VOLTA LIMPA')) + '</span>');
      return;
    }
    const antes = {};
    if (rep) for (const k of rep.corners) antes[k.n] = k.loss;
    let h = '';
    for (let n = 1; n <= c.nCorners; n++) {
      const aoVivo = n in vivo;
      const v = aoVivo ? vivo[n] : antes[n];
      const l = v == null ? '' : sgn(v, 2).replace(/^([+−])0/, '$1');
      const habit = c.habits && c.habits[n];
      h += '<div class="cc ' + lossClass(v) + (aoVivo ? ' live' : temVivo ? ' old' : '') + (habit ? ' habit' : '') +
        '"><b>' + n + '</b><span>' + l + '</span></div>';
    }
    html(R.corners, h);
  }

  // minissetor: pisca o ganho/perda ao sair de cada curva
  const msF = $('msFlash'), pitPrev = $('pitPrev'), treinoChip = $('treinoChip');

  // metas do Time Trial e analise do acerto (caixas da tela de analise)
  function renderExtras(c) {
    const tr = c.treino || {}, ac = c.acerto || {};
    let mt;
    if (!tr.tt) {
      mt = '<p class="dim">' + T('Modo treino e metas só no Time Trial.') + '</p>';
    } else {
      mt = tr.curva
        ? '<p class="a-tc">' + T('Treinando a') + ' <b>' + T('curva ') + tr.curva + '</b>' + (tr.cons ? T(' · variação ±') +
          DEC(tr.cons.seg.toFixed(3)) + ' s' + (tr.cons.bp != null ? ' / ±' + DEC(tr.cons.bp) + ' m' : '') : '') +
          ' <span class="dim">' + T('(T para parar)') + '</span></p>'
        : '<p class="dim">' + T('Selecione uma curva e aperte T para treiná-la.') + '</p>';
      mt += (tr.metas || []).map((m) => '<div class="meta' + (m.feito ? ' ok' : '') + '"><span>' + (m.feito ? '🏆 ' : '') +
        esc(m.texto) + '</span><span class="mbar"><i style="transform:scaleX(' + Math.min(1, m.prog / m.meta).toFixed(2) +
        ')"></i></span><b>' + (m.feito ? T('feita') : m.prog + '/' + m.meta) + '</b></div>').join('') ||
        '<p class="dim">' + T('As metas aparecem depois da primeira volta limpa.') + '</p>';
    }
    html($('aMetas'), mt);
    let at;
    if (!ac.voltas) at = '<p class="dim">' + (ac.novo ? T('Acerto novo: a análise recomeça e aparece depois de 3 voltas lançadas.')
      : T('A análise aparece depois de 3 voltas lançadas.')) + '</p>';
    else if (!ac.ok) at = '<p class="dim">' + (ac.novo ? T('Acerto novo: ') : '') + T('Analisando: %d de 3 voltas.').replace('%d', ac.voltas) + '</p>';
    else if (!ac.achados.length) at = '<p>' + T('Carro equilibrado: nada de subesterço ou sobresterço que se repita.') + '</p>';
    else {
      at = '<ul>' + ac.achados.map((a) => '<li>' + esc(a) + '</li>').join('') + '</ul>';
      if (ac.sugestao) {   // uma mudanca por vez, com o motivo e a proxima da fila
        at += '<ul class="sug"><li>' + esc(ac.sugestao) + ' <span class="dim">(' + esc(ac.motivo) + ')</span></li></ul>';
        if (ac.proxima) at += '<p class="dim">' + T('Depois, se precisar: ') + esc(ac.proxima) + '</p>';
      } else if (ac.aviso) at += '<p class="dim">' + esc(ac.aviso) + '</p>';
    }
    if (ac.comparacao) {   // o que a ultima mudanca de acerto fez
      const v = { melhor: '✅ ', pior: '⚠️ ', passou: '⚠️ ', igual: '➖ ' }[ac.comparacao.veredito] || '';
      at += '<p class="a-comp"><b>' + T('Última mudança:') + '</b> ' + v + esc(ac.comparacao.texto) + '</p>';
    }
    html($('aAcerto'), at);
  }
  let flashTimer = null, lastFlash = null;
  function mostraFlash(f) {
    msF.innerHTML = '<small>' + T('CURVA ') + f.n + '</small>' + sgn(f.d, 3);
    msF.className = 'ms-flash show ' + lossClass(f.d);
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => msF.classList.remove('show'), 1800);
  }
  const esc = (s) => String(s).replace(/[&<>]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[ch]);

  function fmtMeters(v, early, late) {
    if (v == null) return '—';
    if (Math.abs(v) < 5) return T('igual');
    return Math.abs(v) + ' m ' + (v < 0 ? early : late);
  }

  function renderAnalysis(c) {
    const rep = c.report;
    if (rep && (tcSel == null || tcSel > c.nCorners)) tcSel = curvaPadrao();
    if (!rep) {
      txt(R.aSub, c.nCorners ? c.nCorners + T(' curvas mapeadas. A análise aparece ao fim da próxima volta.')
        : T('Faça uma volta limpa para o engenheiro mapear as curvas.'));
      html(R.aRows, '');
    } else {
      const ref = rep.ref ? ' vs ' + (rep.kind === 'recorde' ? T('seu recorde ') : T('sua melhor da sessão ')) + fmtLap(rep.ref) : '';
      txt(R.aSub, T('Volta ') + rep.lap + ': ' + fmtLap(rep.ms) + (rep.valid ? '' : T(' (inválida)')) + ref);
      html(R.aRows, rep.corners.map((k) => {
        const habit = c.habits && c.habits[k.n];
        let obs = k.tip || '';
        if (habit) obs += (obs ? ' · ' : '') + '<span class="habit">' + T('vício: ') + habit + '</span>';
        const dv = k.dv == null ? '—' : Math.abs(k.dv) < 2 ? T('igual') : sgn(k.dv, 0) + ' km/h';
        // frenagem em metros antes da entrada da curva: a sua e a da referencia
        const fr = k.bpEu != null ? k.bpEu + ' m <span class="dim">(ref ' + k.bpRef + ')</span>' : fmtMeters(k.db, T('cedo'), T('tarde'));
        return '<tr data-n="' + k.n + '"' + (k.n === tcSel ? ' class="sel"' : '') + '><td class="n">' + k.n + '</td><td class="' +
          lossClass(k.loss) + '">' + (k.loss == null ? '—' : sgn(k.loss, 3) + ' s') + '</td><td>' + fr +
          '</td><td>' + dv + '</td><td>' + fmtMeters(k.dt, T('antes'), T('tarde')) + '</td><td>' + (obs || '—') + '</td></tr>';
      }).join(''));
    }
    html(R.aLog, log.map((t) => '<li>' + t.replace(/</g, '&lt;') + '</li>').join(''));
    renderExtras(c);
    paintMap();
    if (R.an.classList.contains('show')) carregaTelemetria();
  }

  // ---- mapa da pista
  let coach = null, mapVer = -1, mapData = null;
  function loadMap(ver) {
    mapVer = ver;
    fetch('/mapa').then((r) => r.json()).then((m) => { mapData = m; paintMap(); }).catch(() => { mapVer = -1; });
  }
  function paintMap() {
    const svg = R.aMap;
    if (!mapData || mapData.pts.length < 20) {
      svg.innerHTML = '<text class="empty" x="500" y="235">' + T('O mapa aparece depois da primeira volta limpa.') + '</text>';
      return;
    }
    let pts = mapData.pts, cs = mapData.corners;
    const xs = pts.map((p) => p[0]), zs = pts.map((p) => p[1]);
    let w = Math.max(...xs) - Math.min(...xs), h = Math.max(...zs) - Math.min(...zs);
    const rot = w < h;   // a area e larga: deita a pista se ela for "em pe"
    const tf = (p) => (rot ? [p[1], -p[0]] : [p[0], p[1]]);
    pts = pts.map(tf);
    const cpos = cs.map((k) => tf([k.x, k.z]));
    const X = pts.map((p) => p[0]), Z = pts.map((p) => p[1]);
    const minX = Math.min(...X), minZ = Math.min(...Z);
    w = Math.max(...X) - minX; h = Math.max(...Z) - minZ;
    const s = Math.min(900 / (w || 1), 410 / (h || 1));
    const ox = (1000 - w * s) / 2, oz = (470 - h * s) / 2;
    const P = (p) => [(ox + (p[0] - minX) * s).toFixed(1), (oz + (p[1] - minZ) * s).toFixed(1)];
    const line = pts.map((p) => P(p).join(',')).join(' ');
    const loss = {};
    if (coach && coach.report) for (const k of coach.report.corners) loss[k.n] = k.loss;
    const color = (l) => ({ lbad: '#ff4d5a', lwarn: '#ffd23f', lgood: '#3ddc84' })[lossClass(l)] || '#9aa6b8';
    const p0 = P(pts[0]);
    let out = '<polyline class="trk" points="' + line + ' ' + p0.join(',') + '"/>' +
      '<polyline class="trk2" points="' + line + ' ' + p0.join(',') + '"/>' +
      '<circle cx="' + p0[0] + '" cy="' + p0[1] + '" r="9" fill="#eaf0f8"/>';
    cs.forEach((k, i) => {
      const q = P(cpos[i]);
      out += '<circle data-n="' + k.n + '"' + (k.n === tcSel ? ' class="sel"' : '') + ' cx="' + q[0] + '" cy="' + q[1] +
        '" r="22" fill="' + color(loss[k.n]) + '"/>' + '<text data-n="' + k.n + '" x="' + q[0] + '" y="' + q[1] + '">' + k.n + '</text>';
    });
    svg.innerHTML = out;
  }

  // ---- telemetria comparada: sua volta x referencia na curva escolhida
  const TC = { svg: $('tcGraf'), titulo: $('tcTitulo') };
  let tcSel = null, tcKey = '';
  function curvaPadrao() {   // a curva onde voce mais perdeu
    const cs = coach && coach.report ? coach.report.corners.filter((k) => k.loss != null) : [];
    if (!cs.length) return null;
    return cs.reduce((a, b) => (b.loss > a.loss ? b : a)).n;
  }
  function selecionaCurva(n) {
    tcSel = n;
    if (coach) renderAnalysis(coach);
  }
  function carregaTelemetria() {
    const rep = coach && coach.report;
    if (!rep) {
      tcKey = '';
      TC.svg.innerHTML = '<text class="empty" x="500" y="200">' + T('O gráfico aparece depois de uma volta analisada.') + '</text>';
      return;
    }
    if (tcSel == null || tcSel > coach.nCorners) tcSel = curvaPadrao() || 1;
    const key = rep.lap + ':' + rep.ms + ':' + tcSel;
    if (key === tcKey) return;
    tcKey = key;
    fetch('/telemetria?curva=' + tcSel).then((r) => r.json()).then(desenhaTelemetria).catch(() => { tcKey = ''; });
  }
  function caminho(xs, ys) {
    let d = '';
    for (let i = 0; i < xs.length; i++) d += (i ? 'L' : 'M') + xs[i].toFixed(1) + ' ' + ys[i].toFixed(1);
    return d;
  }
  function desenhaTelemetria(t) {
    if (!t.ok || !t.d.length) {
      TC.svg.innerHTML = '<text class="empty" x="500" y="200">' + T('Sem dados dessa curva na última volta.') + '</text>';
      return;
    }
    const alvo = t.kind === 'recorde' ? T('RECORDE') : T('MELHOR DA SESSÃO');
    txt(TC.titulo, T('TELEMETRIA · CURVA ') + t.n + T(' · VOLTA ') + t.lap + (t.ref ? ' x ' + alvo : ''));
    const L = 78, Rr = 985, d0 = t.d[0], d1 = t.d[t.d.length - 1];
    const X = t.d.map((v) => L + (Rr - L) * (v - d0) / ((d1 - d0) || 1));
    const xDe = (v) => L + (Rr - L) * (v - d0) / ((d1 - d0) || 1);
    // velocidade (y 22..188), pedais (y 214..292), delta de tempo (y 318..388)
    const vs = t.eu.v.concat(t.ref ? t.ref.v : []);
    const vmin = Math.min(...vs) - 8, vmax = Math.max(...vs) + 8;
    const yv = (v) => 188 - (v - vmin) / (vmax - vmin) * 166;
    const yp = (p) => 292 - p * 78;
    let g = '';
    for (const y of [22, 105, 188, 214, 292, 318, 353, 388]) g += '<line class="grade" x1="' + L + '" x2="' + Rr + '" y1="' + y + '" y2="' + y + '"/>';
    g += '<text class="eixo" x="' + (L - 8) + '" y="' + (yv(vmax - 8) + 5) + '" text-anchor="end">' + Math.round(vmax - 8) + '</text>';
    g += '<text class="eixo" x="' + (L - 8) + '" y="' + (yv(vmin + 8) + 5) + '" text-anchor="end">' + Math.round(vmin + 8) + '</text>';
    g += '<text class="rot" x="' + (L - 8) + '" y="106" text-anchor="end">KM/H</text>';
    g += '<text class="rot" x="' + (L - 8) + '" y="257" text-anchor="end">' + T('PEDAIS') + '</text>';
    g += '<text class="rot" x="' + (L - 8) + '" y="357" text-anchor="end">' + T('TEMPO') + '</text>';
    // eixo de distancia: metros a partir da entrada da curva
    const passoM = (d1 - d0) > 500 ? 100 : 50;
    for (let m = Math.ceil(d0 / passoM) * passoM; m <= d1; m += passoM) {
      g += '<text class="eixo" x="' + xDe(m) + '" y="398" text-anchor="middle">' + (m === 0 ? T('entrada') : (m > 0 ? '+' : '') + m + ' m') + '</text>';
    }
    // marcas: freio da referencia, seu freio, apice
    const mk = t.marcas || {};
    // rotulo da referencia a esquerda da linha e o seu a direita, para nao se sobreporem
    const marca = (v, cls, rot, cy, esquerda) => {
      if (v == null || v < d0 || v > d1) return '';
      const x = xDe(v);
      return '<line class="marca ' + cls + '" x1="' + x + '" x2="' + x + '" y1="22" y2="388"/>' +
        (rot ? '<text class="' + cls.replace('m-', 't-') + '" x="' + (esquerda ? x - 6 : x + 6) + '" y="' + cy +
          '" text-anchor="' + (esquerda ? 'end' : 'start') + '">' + rot + '</text>' : '');
    };
    g += marca(mk.apex, 'm-apex', '', 0);
    const refAntes = mk.ref != null && mk.eu != null ? mk.ref <= mk.eu : true;
    if (mk.ref != null) g += marca(mk.ref, 'm-ref', T('freio ref ') + Math.round(-mk.ref) + ' m', 40, refAntes);
    if (mk.eu != null) g += marca(mk.eu, 'm-eu', T('você ') + Math.round(-mk.eu) + ' m', 40, !refAntes);
    // linhas
    if (t.ref) {
      g += '<path class="l-ref" d="' + caminho(X, t.ref.v.map(yv)) + '"/>';
      g += '<path class="l-acel r" d="' + caminho(X, t.ref.thr.map(yp)) + '"/>';
      g += '<path class="l-freio r" d="' + caminho(X, t.ref.brk.map(yp)) + '"/>';
    }
    g += '<path class="l-acel" d="' + caminho(X, t.eu.thr.map(yp)) + '"/>';
    g += '<path class="l-freio" d="' + caminho(X, t.eu.brk.map(yp)) + '"/>';
    g += '<path class="l-eu" d="' + caminho(X, t.eu.v.map(yv)) + '"/>';
    if (t.delta) {
      const dm = Math.max(0.05, ...t.delta.map(Math.abs));
      const yd = (v) => 353 - v / dm * 33;
      g += '<path class="l-delta" d="' + caminho(X, t.delta.map(yd)) + '"/>';
      const fim = t.delta[t.delta.length - 1];
      g += '<text class="t-delta" x="' + (Rr - 4) + '" y="' + (fim > 0 ? 382 : 336) + '" text-anchor="end" fill="' +
        (fim > 0.03 ? '#ff4d5a' : fim < -0.03 ? '#3ddc84' : '#eaf0f8') + '">' + sgn(fim, 3) + ' s</text>';
    }
    TC.svg.innerHTML = g;
  }
  R.aRows.addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-n]');
    if (tr) selecionaCurva(+tr.dataset.n);
  });
  R.aMap.addEventListener('click', (e) => {
    const el = e.target.closest('[data-n]');
    if (el) selecionaCurva(+el.dataset.n);
  });

  // ---- torre de tempos (tecla P ou toque na posicao)
  const TW = { box: $('tower'), sub: $('twSub'), head: $('twHead'), rows: $('twRows') };
  let twUltimo = 0;
  const seg = (ms) => DEC((ms / 1000).toFixed(3));
  function renderTower(t) {
    if (!t || !t.carros.length) {
      txt(TW.sub, T('Sem dados dos outros carros ainda.'));
      html(TW.head, ''); html(TW.rows, '');
      return;
    }
    txt(TW.sub, t.corrida ? (t.volta ? T('Volta ') + t.volta + (t.total ? '/' + t.total : '') : '')
      : T('Classificação pelo melhor tempo'));
    const cols = t.corrida
      ? ['P', T('PILOTO'), T('GAP'), T('INT.'), T('PNEU'), T('PARADAS'), T('ÚLTIMA'), T('MELHOR')]
      : ['P', T('PILOTO'), T('MELHOR'), T('DIF.'), T('PNEU'), T('ÚLTIMA')];
    html(TW.head, cols.map((c) => '<th>' + c + '</th>').join(''));
    html(TW.rows, t.carros.map((k) => {
      const vis = VISUAL[k.comp];
      const pneu = vis ? '<span class="tw-comp" style="border-color:' + vis[1] + '">' + vis[0] + '</span>' +
        (k.idade != null ? k.idade : '') : '—';
      let nome = esc(k.eu ? T('VOCÊ') : k.nome);
      if (k.noPit) nome += ' <em class="tag tw-tag">' + T('NO PIT') + '</em>';
      else if (k.parou) nome += ' <em class="tag tw-tag ok">' + T('◀ parou') + '</em>';
      if (k.pen) nome += ' <em class="tag tw-tag bad">+' + k.pen + 's</em>';
      if (k.fora) nome += ' <em class="tag tw-tag">' + T('FORA') + '</em>';
      const melhor = '<span class="' + (k.roxo ? 'tw-roxo' : '') + '">' + fmtLap(k.melhor) + '</span>';
      let cel;
      if (t.corrida) {
        const gap = k.pos === 1 ? T('LÍDER') : k.voltasAtras ? T('+%d V').replace('%d', k.voltasAtras) : '+' + seg(k.gap);
        const intv = k.pos === 1 ? '—' : k.voltasAtras ? '' : '+' + seg(k.int);
        cel = [k.pos, nome, gap, intv, pneu, k.pits, fmtLap(k.ultima), melhor];
      } else {
        cel = [k.pos, nome, melhor, k.difPole ? '+' + seg(k.difPole) : k.melhor ? '—' : '', pneu, fmtLap(k.ultima)];
      }
      return '<tr class="' + (k.eu ? 'eu' : '') + (k.fora ? ' fora' : '') + '">' +
        cel.map((v, j) => '<td' + (j === 0 ? ' class="n"' : '') + '>' + v + '</td>').join('') + '</tr>';
    }).join(''));
  }
  function toggleTower(force) {
    const open = force === undefined ? !TW.box.classList.contains('show') : force;
    TW.box.classList.toggle('show', open);
    if (open) { toggleAnalysis(false); renderTower(coach && coach.torre); }
  }

  function toggleAnalysis(force) {
    const open = force === undefined ? !R.an.classList.contains('show') : force;
    R.an.classList.toggle('show', open);
    if (open) TW.box.classList.remove('show');
    if (open && coach && coach.mapVer !== mapVer) loadMap(coach.mapVer);
    if (open && coach) renderAnalysis(coach);
  }
  // ---- ajustes do radio (nome, voz, velocidade, volume)
  const C = { box: $('cfg'), idioma: $('cfgIdioma'), nome: $('cfgNome'), nomeJogo: $('cfgNomeJogo'), nomeInfo: $('cfgNomeInfo'), voz: $('cfgVoz'), vel: $('cfgVel'), velTxt: $('cfgVelTxt'),
    vol: $('cfgVol'), volTxt: $('cfgVolTxt'), status: $('cfgStatus'), radio: $('cfgRadio'),
    chiado: $('cfgChiado'), chiadoTxt: $('cfgChiadoTxt'), chiadoRow: $('cfgChiadoRow'), botoes: $('cfgBotoes') };
  let cfgTimer = null;
  let nomeRadio = '';   // como o engenheiro chama o piloto agora (do jogo ou digitado)
  function cfgMostra(r) {
    const a = r.ajustes;
    if (document.activeElement !== C.nome) C.nome.value = a.nome;
    C.nomeJogo.checked = a.nome_jogo;
    nomeRadio = r.nomeAtual || '';
    C.nomeInfo.innerHTML = !a.nome_jogo ? T('O engenheiro usa o nome digitado acima.')
      : r.nomeJogo ? T('No jogo você está como <b>%s</b>: é assim que o engenheiro vai te chamar.').replace('%s', esc(r.nomeJogo))
      : (r.online ? T('Online o jogo manda o seu gamertag, então vale o nome digitado acima.')
        : T('Assim que o jogo mandar os pilotos, o engenheiro usa o seu. Até lá, vale o nome digitado acima.'));
    if (!C.idioma.options.length && r.idiomas) {
      C.idioma.innerHTML = Object.keys(r.idiomas).map((k) => '<option value="' + k + '">' + r.idiomas[k] + '</option>').join('');
    }
    C.idioma.value = a.idioma;
    if (!C.voz.options.length) {
      C.voz.innerHTML = r.vozes.map((v) => '<option value="' + v.id + '">' + v.nome + ' (' + v.tipo + ')</option>').join('');
    }
    C.voz.value = a.voz;
    C.vel.value = a.velocidade;
    C.vol.value = a.volume;
    C.radio.checked = a.radio;
    C.chiado.value = a.chiado;
    cls(C.chiadoRow, 'off', !a.radio);
    txt(C.velTxt, (a.velocidade > 0 ? '+' : '') + a.velocidade + '%');
    txt(C.volTxt, a.volume + '%');
    txt(C.chiadoTxt, a.chiado + '%');
    radioFx = a.radio;
    chiado = a.chiado / 100;
    if (r.botoes && !C.botoes.children.length) {
      C.botoes.innerHTML = Object.keys(r.botoes).map((n) => '<li><b>Action ' + n + '</b>' + r.botoes[n] + '</li>').join('');
    }
    txt(C.status, (r.neural ? '✓ ' : '• ') + r.status.charAt(0).toUpperCase() + r.status.slice(1));
    cls(C.status, 'ok', r.neural);
    cls(C.status, 'off', !r.neural && a.voz !== 'windows');
    neural = r.neural;
    volume = a.volume / 100;
  }
  function cfgCarrega() {
    return fetch('/api/config').then((x) => x.json()).then(cfgMostra).catch(() => txt(C.status, 'Servidor do painel desligado.'));
  }
  function cfgSalva() {
    txt(C.velTxt, (C.vel.value > 0 ? '+' : '') + C.vel.value + '%');
    txt(C.volTxt, C.vol.value + '%');
    txt(C.chiadoTxt, C.chiado.value + '%');
    return fetch('/api/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome: C.nome.value, nome_jogo: C.nomeJogo.checked, voz: C.voz.value, velocidade: +C.vel.value, volume: +C.vol.value,
        radio: C.radio.checked, chiado: +C.chiado.value }),
    }).then((x) => x.json()).then(cfgMostra).catch(() => txt(C.status, T('Não consegui salvar.')));
  }
  function cfgAgenda() { clearTimeout(cfgTimer); cfgTimer = setTimeout(cfgSalva, 350); }
  for (const el of [C.nome, C.vel, C.vol, C.chiado]) el.addEventListener('input', cfgAgenda);
  C.voz.addEventListener('change', cfgSalva);
  C.radio.addEventListener('change', cfgSalva);
  C.nomeJogo.addEventListener('change', cfgSalva);
  C.idioma.addEventListener('change', () => {   // a pagina recarrega no idioma novo (textos, voz e engenheiro)
    fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idioma: C.idioma.value }) }).then(() => location.reload())
      .catch(() => txt(C.status, T('Não consegui salvar.')));
  });
  $('cfgTest').addEventListener('click', () => {
    clearTimeout(cfgTimer);
    cfgSalva().then(() => {
      const n = nomeRadio;
      speak(T('Rádio check') + (n ? ', ' + n : '') + T('. Tô contigo, vamos buscar esse recorde hoje.'), 'normal');
    });
  });
  function toggleCfg(force) {
    const open = force === undefined ? !C.box.classList.contains('show') : force;
    C.box.classList.toggle('show', open);
    if (open) cfgCarrega();
  }
  $('cfgBtn').addEventListener('click', (e) => { e.stopPropagation(); toggleCfg(true); });
  $('wCfg').addEventListener('click', () => toggleCfg(true));
  $('wHide').addEventListener('click', () => { waitHidden = true; cls(E.wait, 'show', false); });
  $('cfgClose').addEventListener('click', () => toggleCfg(false));


  // ------------------------------------------------------------ menu ☰ (o programa)
  // Dentro do app nativo, a pagina fala com ele (fonte, celular, overlay, controles, sair). No
  // celular (navegador comum) o menu so mostra as telas e o idioma.
  const APP = window.__TAURI__ && window.__TAURI__.core;
  const app = (cmd, args) => APP.invoke(cmd, args);
  cls(document.body, 'no-app', !APP);
  const MN = { box: $('menu'), sub: $('mnSub'), nota: $('mnFonteNota'), celular: $('mnCelular'), lan: $('mnLan'),
    overlay: $('mnOverlay'), idioma: $('mnIdiomaTxt') };
  const CT = { box: $('controles'), sub: $('ctSub'), legenda: $('ctLegenda'), rows: $('ctRows') };
  const EV = { box: $('evol'), frame: $('evFrame') };
  const TELAS = () => [MN.box, CT.box, EV.box, TW.box, R.an, C.box];
  let appEstado = null, trocandoFonte = false, menuTimer = null;
  const FONTES = { jogo: T('Jogo'), demo: T('Demo corrida'), tt: T('Demo Time Trial') };

  function fecharTudo() { for (const t of TELAS()) t.classList.remove('show'); clearInterval(menuTimer); }
  function algumaAberta() { return TELAS().some((t) => t.classList.contains('show')); }

  async function atualizaMenu() {
    txt(MN.idioma, LANG_EN ? '🌐 Português' : '🌐 English');
    if (!APP) { txt(MN.sub, T('Painel aberto pela rede')); return; }
    try { appEstado = await app('estado'); } catch (e) { return; }
    const a = appEstado;
    for (const b of MN.box.querySelectorAll('[data-fonte]')) {
      cls(b, 'on', b.dataset.fonte === a.fonte);
      b.disabled = trocandoFonte;
    }
    txt(MN.sub, T('Fonte: ') + (FONTES[a.fonte] || a.fonte) + (a.rodando ? '' : ' · ' + T('iniciando…')));
    if (!trocandoFonte) txt(MN.nota, a.erro || '');
    cls(MN.celular, 'on', a.compartilhar);
    cls(MN.overlay, 'on', a.overlay);
    cls(MN.lan, 'show', a.compartilhar);
    html(MN.lan, a.lan ? T('No celular ou tablet, na mesma rede, abra:') + '<br><b>' + esc(a.lan) + '</b>'
      : a.compartilhar ? T('Ligando…') : '');
  }
  function toggleMenu(force) {
    const open = force === undefined ? !MN.box.classList.contains('show') : force;
    if (open) { fecharTudo(); MN.box.classList.add('show'); atualizaMenu(); menuTimer = setInterval(atualizaMenu, 1000); }
    else { MN.box.classList.remove('show'); clearInterval(menuTimer); }
  }
  function abrirTela(nome) {
    fecharTudo();
    if (nome === 'menu') toggleMenu(true);
    else if (nome === 'torre') toggleTower(true);
    else if (nome === 'analise') toggleAnalysis(true);
    else if (nome === 'ajustes') toggleCfg(true);
    else if (nome === 'controles') abrirControles();
    else if (nome === 'evolucao') {
      if (!EV.frame.getAttribute('src')) EV.frame.src = '/evolucao';
      else try { EV.frame.contentWindow.location.reload(); } catch (e) { /* ainda carregando */ }
      EV.box.classList.add('show');
    }
  }
  for (const b of document.querySelectorAll('[data-tela]')) {
    b.addEventListener('click', (e) => { e.stopPropagation(); abrirTela(b.dataset.tela); });
  }
  $('menuBtn').addEventListener('click', (e) => { e.stopPropagation(); toggleMenu(); });
  $('mnClose').addEventListener('click', () => toggleMenu(false));
  $('evClose').addEventListener('click', () => EV.box.classList.remove('show'));
  $('ctClose').addEventListener('click', () => CT.box.classList.remove('show'));
  for (const b of MN.box.querySelectorAll('[data-fonte]')) {
    b.addEventListener('click', async () => {
      if (!APP || trocandoFonte || (appEstado && appEstado.fonte === b.dataset.fonte && appEstado.rodando)) return;
      trocandoFonte = true;
      txt(MN.nota, T('Trocando a fonte… o painel reconecta sozinho.'));
      atualizaMenu();
      try { await app('trocar_fonte', { fonte: b.dataset.fonte }); txt(MN.nota, ''); }
      catch (e) { txt(MN.nota, String(e)); }
      trocandoFonte = false;
      atualizaMenu();
    });
  }
  MN.celular.addEventListener('click', async () => {
    if (!APP || !appEstado) return;
    cls(MN.celular, 'on', !appEstado.compartilhar);
    txt(MN.nota, T('Reiniciando o painel… ele reconecta sozinho.'));
    try { await app('compartilhar', { ligar: !appEstado.compartilhar }); txt(MN.nota, ''); }
    catch (e) { txt(MN.nota, String(e)); }
    atualizaMenu();
  });
  MN.overlay.addEventListener('click', async () => { if (APP) { await app('alternar_overlay'); atualizaMenu(); } });
  $('mnTela').addEventListener('click', () => APP && app('tela_cheia'));
  $('mnSair').addEventListener('click', () => APP && app('sair'));
  $('mnIdioma').addEventListener('click', () => {
    fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idioma: LANG_EN ? 'pt' : 'en' }) })
      .then(() => (APP ? app('idioma_mudou') : null)).then(() => location.reload()).catch(() => {});
  });

  // ---- controles e teclas (gravar)
  const ACOES = [['menu', T('Abrir o menu')], ['falar', T('Falar com o engenheiro')], ['torre', T('Torre de tempos')],
    ['analise', T('Análise da volta')], ['overlay', T('Overlay liga/desliga')], ['fechar', T('Fechar as telas')]];
  const BOTAO_NOME = { a: 'A', b: 'B', x: 'X', y: 'Y', lb: 'LB', rb: 'RB', ls: 'L3', rs: 'R3', start: 'Start',
    back: 'View', cima: '↑', baixo: '↓', esquerda: '←', direita: '→' };
  let ctMapa = null, gravandoTecla = null;
  function acaoNome(a) {
    if (a.startsWith('pergunta:')) {
      const n = a.slice(9);
      return T('Pergunta') + ' ' + n + (PERGUNTAS[n] ? ': ' + PERGUNTAS[n] : '');
    }
    const x = ACOES.find((q) => q[0] === a);
    return x ? x[1] : a;
  }
  const PERGUNTAS = { 1: T('Pneus'), 2: T('Gaps'), 3: T('Combustível e bateria'), 4: T('Onde estou perdendo'),
    5: T('Clima e pit'), 6: T('Repetir a última'), 7: T('Silêncio (só o essencial)'), 8: T('Estratégia de pit'),
    9: T('Metas e treino'), 10: T('Acerto do carro') };
  function renderControles() {
    if (!ctMapa) return;
    const todas = ACOES.map((a) => a[0]).concat(Object.keys(PERGUNTAS).map((n) => 'pergunta:' + n));
    const tecla = (a) => (ctMapa.teclas.find((t) => t[1] === a) || [])[0];
    const botao = (a) => (ctMapa.controle.find((t) => t[1] === a) || [])[0];
    const mod = BOTAO_NOME[ctMapa.controle_modificador] || ctMapa.controle_modificador;
    html(CT.legenda, T('Funcionam com o jogo em foco. No controle, segure %s e aperte o botão.').replace('%s', '<b>' + esc(mod) + '</b>'));
    html(CT.rows, todas.map((a) => {
      const t = tecla(a), b = botao(a);
      return '<tr><td>' + esc(acaoNome(a)) + '</td>' +
        '<td><span class="ct-cel"><kbd class="' + (t ? '' : 'vazio') + '">' + esc(t || '—') + '</kbd>' +
        '<button type="button" data-gt="' + a + '">' + T('gravar') + '</button></span></td>' +
        '<td><span class="ct-cel"><kbd class="' + (b ? '' : 'vazio') + '">' + esc(b ? mod + ' + ' + (BOTAO_NOME[b] || b) : '—') + '</kbd>' +
        '<button type="button" data-gb="' + a + '">' + T('gravar') + '</button></span></td></tr>';
    }).join(''));
  }
  async function abrirControles() {
    if (!APP) return;
    CT.box.classList.add('show');
    try { ctMapa = await app('controles'); } catch (e) { return; }
    try { appEstado = await app('estado'); } catch (e) { /* segue */ }
    txt(CT.sub, appEstado && appEstado.controle ? T('Controle conectado: ') + appEstado.controle
      : T('Nenhum controle XInput conectado (Xbox, ou PlayStation via Steam Input).'));
    renderControles();
  }
  CT.rows.addEventListener('click', async (e) => {
    const bt = e.target.closest('button');
    if (!bt) return;
    if (bt.dataset.gt) {          // tecla: a proxima combinacao apertada aqui
      gravandoTecla = bt.dataset.gt;
      cls(bt, 'gravando', true);
      bt.textContent = T('aperte Ctrl/Alt + tecla…');
    } else if (bt.dataset.gb) {   // botao: o proximo botao do controle (o app le direto)
      cls(bt, 'gravando', true);
      bt.textContent = T('aperte o botão…');
      try { await app('gravar_botao', { acao: bt.dataset.gb }); } catch (err) { txt(CT.sub, String(err)); }
      ctMapa = await app('controles');
      renderControles();
    }
  });
  $('ctPadrao').addEventListener('click', async () => {
    if (!APP) return;
    await app('restaurar_controles');
    ctMapa = await app('controles');
    renderControles();
  });
  addEventListener('keydown', async (e) => {   // capturando a tecla para gravar
    if (!gravandoTecla) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) return;
    const acao = gravandoTecla;
    gravandoTecla = null;
    if (e.key === 'Escape') { renderControles(); return; }
    if (!e.ctrlKey && !e.altKey && !e.shiftKey) {
      txt(CT.sub, T('Use Ctrl, Alt ou Shift junto, para não atrapalhar quando você digita.'));
      renderControles();
      return;
    }
    const cod = e.code.startsWith('Key') ? e.code.slice(3) : e.code.startsWith('Digit') ? e.code.slice(5) : e.code;
    const tecla = (e.ctrlKey ? 'Ctrl+' : '') + (e.altKey ? 'Alt+' : '') + (e.shiftKey ? 'Shift+' : '') + cod;
    try { await app('gravar_tecla', { acao, tecla }); } catch (err) { txt(CT.sub, String(err)); }
    ctMapa = await app('controles');
    renderControles();
  }, true);

  R.mode.addEventListener('click', (e) => { e.stopPropagation(); cycleMode(); });
  R.corners.addEventListener('click', () => toggleAnalysis(true));
  $('aClose').addEventListener('click', () => toggleAnalysis(false));
  $('twClose').addEventListener('click', () => toggleTower(false));
  E.pos.closest('.kv').addEventListener('click', (e) => { e.stopPropagation(); toggleTower(true); });
  addEventListener('keydown', (e) => {
    const k = e.key.toLowerCase();
    if (k === 'escape') { if (algumaAberta()) fecharTudo(); else toggleMenu(true); return; }
    if (e.target.closest && e.target.closest('input, select, textarea')) return;   // digitando o nome
    if ((k === 'arrowleft' || k === 'arrowright') && R.an.classList.contains('show') && coach && coach.nCorners) {
      const n = coach.nCorners, atual = tcSel || 1;
      selecionaCurva(k === 'arrowright' ? atual % n + 1 : (atual - 2 + n) % n + 1);
      return;
    }
    if (/^[0-9]$/.test(k)) {   // mesmas perguntas dos botoes do volante (0 = botao 10)
      fetch('/api/pergunta', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ acao: k === '0' ? 10 : +k }) }).catch(() => {});
    } else if (k === 't') {    // treinar a curva selecionada na analise (so no Time Trial)
      const curva = R.an.classList.contains('show') && tcSel ? tcSel : null;
      fetch('/api/treino', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curva }) }).catch(() => {});
    } else if (k === 'a') toggleAnalysis();
    else if (k === 'p') toggleTower();
    else if (k === 'm') ouvir();
    else if (k === 'v') cycleMode();
    else if (k === 'c') toggleCfg();
    else if (k === 'e') abrirTela('evolucao');
  });
  setMode(mode);

  // ------------------------------------------------------------ eventos
  let lastSeq, toastTimer, lightsTimer;
  function handleEvent(ev) {
    const seq = ev ? ev.seq : 0;
    if (lastSeq === undefined) { lastSeq = seq; return; }   // ignora evento antigo ao abrir
    if (seq === lastSeq) return;
    lastSeq = seq;
    if (!ev) return;
    if (ev.code === 'STLG') {
      cls(E.lights, 'show', true);
      lightEls.forEach((el, i) => cls(el, 'on', i < ev.n));
      clearTimeout(lightsTimer);
      lightsTimer = setTimeout(() => cls(E.lights, 'show', false), 12000);
      return;
    }
    if (ev.code === 'LGOT') cls(E.lights, 'show', false);
    if (ev.text) {
      txt(E.toast, ev.text);
      cls(E.toast, 'show', true);
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => cls(E.toast, 'show', false), 4500);
    }
  }

  // ------------------------------------------------------------ dados
  let state = null, dirty = false, lastMsg = 0;
  function connect() {
    const es = new EventSource('/stream');
    es.onmessage = (e) => {
      state = JSON.parse(e.data); lastMsg = performance.now(); dirty = true;
      if (state.lang && state.lang !== (LANG_EN ? 'en' : 'pt')) location.reload();   // idioma trocado no menu ou nos ajustes
    };
  }
  connect();

  function frame() {
    fit();
    if (dirty && state) { dirty = false; render(state); }
    pump();
    if (performance.now() - lastMsg > 2500) {
      cls(E.wait, 'show', true);
      txt(E.waitMsg, T('O servidor do painel está desligado. Abra o PainelF1.exe e depois, no jogo:'));
      txt(E.conn, T('SEM SINAL'));
      cls(E.conn, 'live', false);
      cls(E.conn, 'demo', false);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  // esconde o cursor quando parado
  let idleTimer;
  addEventListener('mousemove', () => {
    document.body.classList.remove('idle');
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => document.body.classList.add('idle'), 3000);
  });
})();
