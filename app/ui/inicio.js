// Tela "Iniciando…" do painel: aparece enquanto o nucleo sobe e troca sozinha para o painel.
// Se der erro (porta ocupada etc.), mostra o motivo, a escolha da fonte e "tentar de novo".
(() => {
  'use strict';
  const invoke = window.__TAURI__.core.invoke;
  const $ = (id) => document.getElementById(id);
  const TXT = {
    pt: { sub: 'Telemetria e engenheiro de corrida', iniciando: 'Iniciando', erro: 'Não deu para iniciar',
      jogo: 'Jogo', demo: 'Demo corrida', tt: 'Demo Time Trial', deNovo: 'Tentar de novo', sair: 'Sair' },
    en: { sub: 'Telemetry and race engineer', iniciando: 'Starting', erro: "Couldn't start",
      jogo: 'Game', demo: 'Demo race', tt: 'Demo Time Trial', deNovo: 'Try again', sair: 'Quit' },
  };
  let ocupado = false;

  async function atualizar() {
    let e;
    try { e = await invoke('estado'); } catch (err) { return; }
    const t = TXT[e.idioma] || TXT.pt;
    $('sub').textContent = t.sub;
    if (e.rodando) { location.href = e.url; return; }   // nucleo pronto: vira o painel
    const comErro = !!e.erro && !ocupado;
    $('caixa').classList.toggle('erro', comErro);
    $('status').textContent = comErro ? t.erro : t.iniciando;
    $('msg').textContent = e.erro || '';
    for (const b of document.querySelectorAll('[data-f]')) {
      b.textContent = t[b.dataset.f];
      b.classList.toggle('on', b.dataset.f === e.fonte);
    }
    $('bDeNovo').textContent = t.deNovo;
    $('bSair').textContent = t.sair;
  }

  async function tentar(cmd, args) {
    ocupado = true;
    $('caixa').classList.remove('erro');
    try { await invoke(cmd, args); } catch (err) { /* o erro volta no estado */ }
    ocupado = false;
    atualizar();
  }

  for (const b of document.querySelectorAll('[data-f]')) b.addEventListener('click', () => tentar('trocar_fonte', { fonte: b.dataset.f }));
  $('bDeNovo').addEventListener('click', () => tentar('tentar_de_novo'));
  $('bSair').addEventListener('click', () => invoke('sair'));
  atualizar();
  setInterval(atualizar, 500);
})();
