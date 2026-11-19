// Janela de inicio do app nativo: escolhe o modo, mostra o estado do nucleo e os atalhos.
(() => {
  'use strict';
  const invoke = window.__TAURI__.core.invoke;
  const $ = (id) => document.getElementById(id);
  const TXT = {
    pt: {
      sub: 'Telemetria e engenheiro de corrida',
      modos: {
        painel: ['Iniciar painel', 'Recebe a telemetria do F1 25'],
        demo: ['Demo: corrida simulada', 'Tudo funcionando sem abrir o jogo'],
        tt: ['Demo: Time Trial', 'Modo treino e metas do dia'],
        lan: ['Painel no celular ou tablet', 'Libera o painel na rede local'],
      },
      rodando: 'RODANDO', subindo: 'INICIANDO…', erro: 'ERRO',
      esperando: 'Esperando o F1 25 na porta UDP 20777. No jogo: Telemetria → UDP ligado, IP 127.0.0.1, porta 20777, 60 Hz.',
      demo: 'Dados simulados, sem o jogo. O demo usa um histórico separado do seu.',
      lan: 'No celular ou tablet, na mesma rede, abra:', lanDica: 'Se não abrir, libere o Painel F1 25 no firewall do Windows.',
      painel: 'Abrir painel', overlay: 'Overlay', evolucao: 'Evolução',
      atalhos: 'Funcionam com o jogo em foco:', controle: 'Controle', semControle: 'nenhum controle XInput conectado',
      segure: 'segure %s +', bandeja: 'Fechar esta janela deixa o painel rodando na bandeja.', sair: 'Sair', idioma: 'English',
      acoes: { falar: 'falar com o engenheiro', torre: 'torre', analise: 'análise', overlay: 'overlay', fechar: 'fechar telas',
        ajustes: 'ajustes', painel: 'painel' },
      pergunta: 'pergunta %s',
    },
    en: {
      sub: 'Telemetry and race engineer',
      modos: {
        painel: ['Start dashboard', 'Receives F1 25 telemetry'],
        demo: ['Demo: simulated race', 'Everything working without the game'],
        tt: ['Demo: Time Trial', 'Practice mode and daily goals'],
        lan: ['Dashboard on phone or tablet', 'Shares the dashboard on your network'],
      },
      rodando: 'RUNNING', subindo: 'STARTING…', erro: 'ERROR',
      esperando: 'Waiting for F1 25 on UDP port 20777. In the game: Telemetry → UDP on, IP 127.0.0.1, port 20777, 60 Hz.',
      demo: 'Simulated data, no game needed. The demo uses a history separate from yours.',
      lan: 'On your phone or tablet, on the same network, open:', lanDica: 'If it doesn\'t load, allow Painel F1 25 through the Windows firewall.',
      painel: 'Open dashboard', overlay: 'Overlay', evolucao: 'Progress',
      atalhos: 'They work with the game in focus:', controle: 'Controller', semControle: 'no XInput controller connected',
      segure: 'hold %s +', bandeja: 'Closing this window keeps the dashboard running in the tray.', sair: 'Quit', idioma: 'Português',
      acoes: { falar: 'talk to the engineer', torre: 'timing tower', analise: 'analysis', overlay: 'overlay', fechar: 'close screens',
        ajustes: 'settings', painel: 'dashboard' },
      pergunta: 'question %s',
    },
  };
  let E = null, iniciando = false;

  function acaoTxt(t, a) {
    if (a.startsWith('pergunta:')) return t.pergunta.replace('%s', a.slice(9));
    return t.acoes[a] || a;
  }

  function render() {
    if (!E) return;
    const t = TXT[E.idioma] || TXT.pt;
    document.documentElement.lang = E.idioma === 'en' ? 'en' : 'pt-BR';
    $('sub').textContent = t.sub;
    $('modos').innerHTML = Object.keys(t.modos).map((m) => {
      const ativo = m === E.modo;
      const est = !ativo ? '' : E.erro ? '<span class="estado erro">' + t.erro + '</span>'
        : (E.iniciando || iniciando) ? '<span class="estado sub">' + t.subindo + '</span>'
          : E.rodando ? '<span class="estado ok">● ' + t.rodando + '</span>' : '';
      return '<div class="modo' + (ativo ? ' ativo' : '') + '" data-m="' + m + '"><b>' + t.modos[m][0] + '</b><span>' +
        t.modos[m][1] + '</span>' + est + '</div>';
    }).join('');
    let info;
    if (E.erro) info = '<span class="erro">' + E.erro + '</span>';
    else if (E.modo === 'lan') info = t.lan + '<div class="lan">' + (E.lan || '…') + '</div>' + t.lanDica;
    else if (E.modo === 'demo' || E.modo === 'tt') info = t.demo;
    else info = t.esperando;
    $('info').innerHTML = info;
    $('bPainel').textContent = t.painel;
    $('bOverlay').textContent = t.overlay + (E.overlay ? ' ✓' : '');
    $('bOverlay').classList.toggle('on', E.overlay);
    $('bEvolucao').textContent = t.evolucao;
    const teclas = E.teclas.filter(([, a]) => !a.startsWith('pergunta:') || a === 'pergunta:1')
      .map(([k, a]) => '<b>' + k + '</b> ' + acaoTxt(t, a)).join(' · ');
    $('atalhos').innerHTML = t.atalhos + '<br>' + teclas + ' · <b>Ctrl+Alt+1…0</b> ' + t.pergunta.replace(' %s', 's') +
      '<br><b>' + t.controle + ':</b> ' + (E.controle ? E.controle + ' ✓' : t.semControle);
    $('bandeja').textContent = t.bandeja;
    $('bIdioma').textContent = '🌐 ' + t.idioma;
    $('bSair').textContent = t.sair;
  }

  async function atualizar() {
    try { E = await invoke('estado'); render(); } catch (e) { /* app fechando */ }
  }

  $('modos').addEventListener('click', async (ev) => {
    const el = ev.target.closest('[data-m]');
    if (!el || iniciando) return;
    iniciando = true;
    E.modo = el.dataset.m; E.erro = null; render();
    try { await invoke('iniciar', { modo: el.dataset.m }); } catch (e) { /* o erro aparece no estado */ }
    iniciando = false;
    atualizar();
  });
  $('bPainel').addEventListener('click', () => invoke('abrir_painel'));
  $('bEvolucao').addEventListener('click', () => invoke('abrir_evolucao'));
  $('bOverlay').addEventListener('click', async () => { await invoke('alternar_overlay'); atualizar(); });
  $('bIdioma').addEventListener('click', async () => {
    try { await invoke('trocar_idioma', { lang: E.idioma === 'en' ? 'pt' : 'en' }); } catch (e) { /* nucleo parado */ }
    atualizar();
  });
  $('bSair').addEventListener('click', () => invoke('sair'));
  atualizar();
  setInterval(atualizar, 1000);
})();
