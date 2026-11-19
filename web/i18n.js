// Idioma da pagina. O servidor entrega o <html lang="en"> quando o painel esta em ingles;
// T('texto em portugues') devolve a traducao, e os textos fixos do HTML sao traduzidos aqui.
// Para conferir se falta alguma traducao: uv run tools/checar_traducao.py
(() => {
  'use strict';
  const EN = /*EN*/{
    "DIANT. ESQ.": "FRONT L", "DIANT. DIR.": "FRONT R", "TRAS. ESQ.": "REAR L", "TRAS. DIR.": "REAR R",
    "INTERNA": "INNER", "PRESSÃO": "PRESSURE", "FREIO": "BRAKE",
    "ÚLTIMA": "LAST", "MELHOR": "BEST", "À FRENTE": "AHEAD", "LÍDER": "LEADER", "PUNIÇÕES": "PENALTIES",
    "AVISOS": "WARNINGS",
    "Asa diant. E": "Front wing L", "Asa diant. D": "Front wing R", "Asa traseira": "Rear wing",
    "Assoalho": "Floor", "Difusor": "Diffuser", "Câmbio": "Gearbox", "Motor": "Engine",
    "DIF.": "DIFF", "MOTOR": "ENGINE", "JANELA PIT": "PIT WINDOW", "FALHA DRS": "DRS FAULT",
    "FALHA ERS": "ERS FAULT", "MOTOR QUEBRADO": "ENGINE BLOWN",
    "POBRE": "LEAN", "PADRÃO": "STANDARD", "RICA": "RICH", "MÁXIMA": "MAX",
    "NENHUM": "NONE", "MÉDIO": "MEDIUM",
    "Macio": "Soft", "Médio": "Medium", "Duro": "Hard", "Intermediário": "Intermediate", "Chuva": "Wet",
    "Nenhuma telemetria chegando. No jogo, abra:": "No telemetry coming in. In the game, open:",
    "SEM SINAL": "NO SIGNAL", "AO VIVO · UDP ": "LIVE · UDP ", "Sem sessão": "No session",
    " · chuva ": " · rain ", "% em ": "% in ",
    "VOLTA DE FORMAÇÃO": "FORMATION LAP", "BANDEIRA AMARELA": "YELLOW FLAG", "BANDEIRA AZUL": "BLUE FLAG",
    "BANDEIRA VERDE": "GREEN FLAG",
    "FALHA": "FAULT", "MODO RETA": "STRAIGHT MODE", "ABERTO": "OPEN", "DISPONÍVEL": "AVAILABLE", "em ": "in ",
    "ATIVO": "ACTIVE", "LIMITADOR": "LIMITER", "NOS BOXES": "IN THE GARAGE",
    " volta": " lap", " voltas": " laps",
    "VOZ: TUDO": "VOICE: ALL", "VOZ: SÓ IMPORTANTE": "VOICE: IMPORTANT ONLY", "VOZ: DESLIGADA": "VOICE: OFF",
    "Clique aqui (ou em qualquer lugar do painel) para ativar a voz do engenheiro.":
      "Click here (or anywhere on the dashboard) to turn on the engineer's voice.",
    "Rádio ativado.": "Radio on.",
    "PIT AGORA → ": "PIT NOW → ", " · atrás de ": " · behind ", "TREINO · C": "PRACTICE · T",
    "há %d s": "%d s ago",
    " CURVAS MAPEADAS · ANÁLISE APÓS A PRÓXIMA VOLTA": " CORNERS MAPPED · ANALYSIS AFTER THE NEXT LAP",
    "AS CURVAS SÃO MAPEADAS NA PRIMEIRA VOLTA LIMPA": "CORNERS ARE MAPPED ON THE FIRST CLEAN LAP",
    "Modo treino e metas só no Time Trial.": "Practice mode and goals are Time Trial only.",
    "Treinando a": "Practising", "curva ": "turn ", " · variação ±": " · spread ±", "(T para parar)": "(T to stop)",
    "Selecione uma curva e aperte T para treiná-la.": "Select a corner and press T to practise it.",
    "feita": "done",
    "As metas aparecem depois da primeira volta limpa.": "Goals show up after the first clean lap.",
    "A análise aparece depois de 3 voltas lançadas.": "The analysis shows up after 3 flying laps.",
    "Analisando: %d de 3 voltas.": "Analysing: %d of 3 laps.",
    "Carro equilibrado: nada de subesterço ou sobresterço que se repita.":
      "Car is balanced: no understeer or oversteer that keeps repeating.",
    "Depois, se precisar: ": "Next, if needed: ",
    "Última mudança:": "Last change:",
    "CURVA ": "TURN ", "igual": "same",
    " curvas mapeadas. A análise aparece ao fim da próxima volta.": " corners mapped. The analysis shows up at the end of the next lap.",
    "Faça uma volta limpa para o engenheiro mapear as curvas.": "Do a clean lap so the engineer can map the corners.",
    "seu recorde ": "your record ", "sua melhor da sessão ": "your session best ", "Volta ": "Lap ",
    " (inválida)": " (invalid)", "vício: ": "habit: ", "cedo": "early", "tarde": "late", "antes": "earlier",
    "O mapa aparece depois da primeira volta limpa.": "The map shows up after the first clean lap.",
    "O gráfico aparece depois de uma volta analisada.": "The chart shows up after an analysed lap.",
    "Sem dados dessa curva na última volta.": "No data for this corner on the last lap.",
    "RECORDE": "RECORD", "MELHOR DA SESSÃO": "SESSION BEST", "TELEMETRIA · CURVA ": "TELEMETRY · TURN ",
    " · VOLTA ": " · LAP ", "PEDAIS": "PEDALS", "TEMPO": "TIME", "entrada": "entry", "freio ref ": "ref brake ",
    "você ": "you ",
    "O engenheiro usa o nome digitado acima.": "The engineer uses the name typed above.",
    "No jogo você está como <b>%s</b>: é assim que o engenheiro vai te chamar.":
      "In the game you're <b>%s</b>: that's what the engineer will call you.",
    "Online o jogo manda o seu gamertag, então vale o nome digitado acima.":
      "Online the game sends your gamertag, so the name typed above is used.",
    "Assim que o jogo mandar os pilotos, o engenheiro usa o seu. Até lá, vale o nome digitado acima.":
      "As soon as the game sends the drivers, the engineer uses yours. Until then, the name typed above is used.",
    "Não consegui salvar.": "Couldn't save.",
    "Rádio check": "Radio check", ". Tô contigo, vamos buscar esse recorde hoje.": ". I'm with you, let's go get that record today.",
    "O servidor do painel está desligado. Abra o PainelF1.exe e depois, no jogo:":
      "The dashboard server is off. Open PainelF1.exe and then, in the game:",

    "Evolução F1 25": "F1 25 Progress", "← Painel": "← Dashboard", "Evolução": "Progress",
    "Carregando…": "Loading…", "Pista": "Track",
    "travar as rodas": "locking the wheels", "frear cedo demais": "braking too early",
    "frear tarde e passar do ponto": "braking late and overshooting", "contornar devagar demais": "too slow through the corner",
    "acelerar tarde na saída": "getting on the power late", "patinar na saída": "wheelspin on exit",
    "entrar rápido demais": "carrying too much speed in",
    "O gráfico aparece a partir da segunda sessão nesta pista.": "The chart shows up from your second session at this track.",
    "Média ": "Average ", "Melhor ": "Best ", "Melhor volta e média por sessão": "Best lap and average per session",
    "Melhor volta da sessão": "Session best lap", "Média das voltas limpas": "Average of clean laps",
    "Nenhuma volta registrada nesta pista ainda.": "No laps recorded at this track yet.",
    "Recorde pessoal": "Personal best", "sua melhor volta aqui": "your best lap here", "Volta ideal": "Ideal lap",
    "seus melhores trechos somados: %s s para buscar": "your best sections added up: %s s to find",
    "soma dos seus melhores trechos": "sum of your best sections",
    "Última sessão": "Last session", "média ": "average ", "Voltas registradas": "Laps recorded",
    "em %d sessões": "over %d sessions", "em 1 sessão": "in 1 session",
    "EVOLUÇÃO POR SESSÃO": "PROGRESS PER SESSION", "CONQUISTAS DO MODO TREINO": "PRACTICE MODE ACHIEVEMENTS",
    "CURVA A CURVA": "CORNER BY CORNER", "CURVA": "TURN", "MELHOR TRECHO": "BEST SECTION",
    "MÉDIA RECENTE": "RECENT AVERAGE", "TEMPO PARA BUSCAR": "TIME TO FIND", "TENDÊNCIA": "TREND", "VÍCIO": "HABIT",
    "estável": "steady", " s melhor": " s better", " s pior": " s worse", "% das voltas": "% of laps",
    "Tendência compara suas 10 últimas voltas limpas com as 10 anteriores. ● = onde você mais tem tempo para ganhar.":
      "Trend compares your last 10 clean laps with the 10 before them. ● = where you have the most time to gain.",
    "SESSÕES": "SESSIONS", "DATA": "DATE", "TIPO": "TYPE", "VOLTAS": "LAPS", "MÉDIA": "AVERAGE",
    "CONSISTÊNCIA": "CONSISTENCY",
    "Não consegui ler o histórico. O servidor do painel está aberto?": "Couldn't read the history. Is the dashboard server running?",
    "Nenhuma volta registrada ainda.": "No laps recorded yet.",
    "Corra no F1 25 com o painel aberto: cada volta limpa entra aqui automaticamente.":
      "Drive in F1 25 with the dashboard open: every clean lap shows up here automatically.",

    "Painel F1 25": "Painel F1 25", "VOLTA": "LAP", "PISTA": "TRACK", "AR": "AIR", "ACEL.": "THROT.",
    "VOLANTE": "STEERING", "EMBREAGEM": "CLUTCH", "VOLTA ATUAL": "CURRENT LAP", "INVÁLIDA": "INVALID",
    "DELTA P/ MELHOR": "DELTA TO BEST", "COLHIDO": "HARVESTED", "USADO": "DEPLOYED", "COMBUSTÍVEL": "FUEL",
    "voltas": "laps", "de sobra": "to spare", "TANQUE": "TANK", "POTÊNCIA": "POWER",
    "RÁDIO DO ENGENHEIRO": "ENGINEER RADIO", "⚙ AJUSTES": "⚙ SETTINGS",
    "Faça uma volta limpa: o engenheiro monta sua referência e começa a analisar cada curva.":
      "Do a clean lap: the engineer builds your reference and starts analysing every corner.",
    "PNEUS E FREIOS": "TYRES AND BRAKES", "DANOS": "DAMAGE", "DESGASTE DA UNIDADE DE POTÊNCIA": "POWER UNIT WEAR",
    "ANÁLISE POR CURVA": "CORNER ANALYSIS", "Sem voltas analisadas ainda.": "No laps analysed yet.",
    "EVOLUÇÃO →": "PROGRESS →", "FECHAR ✕": "CLOSE ✕", "ganhou": "gained", "perdeu >0,06 s": "lost >0.06 s",
    "perdeu >0,15 s": "lost >0.15 s", "TELEMETRIA COMPARADA": "TELEMETRY COMPARISON", "sua volta": "your lap",
    "referência": "reference", "· toque numa curva ou use ← →": "· tap a corner or use ← →",
    "METAS · TIME TRIAL": "GOALS · TIME TRIAL", "ACERTO DO CARRO": "CAR SETUP", "PERDA": "LOSS",
    "FRENAGEM": "BRAKING", "VEL. MÍN.": "MIN SPEED", "ACELERADOR": "THROTTLE", "OBSERVAÇÃO": "NOTE",
    "ÚLTIMAS MENSAGENS": "LATEST MESSAGES", "RÁDIO E VOZ": "RADIO AND VOICE", "SEU NOME NO RÁDIO": "YOUR NAME ON THE RADIO",
    "Chamar pelo nome do piloto que estou usando no jogo": "Call me by the name of the driver I'm using in the game",
    "VOZ DO ENGENHEIRO": "ENGINEER VOICE", "VELOCIDADE DA FALA": "SPEECH SPEED", "VOLUME": "VOLUME",
    "Som de rádio de equipe (bipes, voz filtrada e chiado)": "Team radio sound (beeps, filtered voice and static)",
    "CHIADO": "STATIC",
    "BOTÕES DO VOLANTE (UDP ACTION) · OU TECLAS 1–9 E 0 (=10) NO PAINEL":
      "WHEEL BUTTONS (UDP ACTION) · OR KEYS 1–9 AND 0 (=10) ON THE DASHBOARD",
    "▶ TESTAR VOZ": "▶ TEST VOICE",
    "As vozes naturais usam a internet (serviço de voz da Microsoft). Sem conexão, o engenheiro fala com a voz do Windows.":
      "The natural voices use the internet (Microsoft's voice service). Offline, the engineer uses the Windows voice.",
    "Aguardando o F1 25": "Waiting for F1 25", "Configurações →": "Settings →", "Telemetria": "Telemetry",
    "Telemetria UDP:": "UDP Telemetry:", "Ligado": "On", "Endereço IP:": "IP Address:", "· Porta:": "· Port:",
    "Taxa de envio:": "Send rate:", "60 Hz": "60 Hz", "Formato UDP:": "UDP Format:", "ou": "or",
    "O painel acende sozinho quando você entrar na pista. Para testar sem o jogo, escolha o Demo no menu do programa.":
      "The dashboard lights up by itself when you go out on track. To try it without the game, pick Demo in the program menu.",
    "⚙ AJUSTES DO RÁDIO": "⚙ RADIO SETTINGS", "📈 EVOLUÇÃO": "📈 PROGRESS", "VER O PAINEL ✕": "SHOW THE DASHBOARD ✕",
    "Onde você volta se parar agora": "Where you rejoin if you stop now",
    "Ajustes do rádio (tecla C)": "Radio settings (key C)",
    "Toque para abrir a análise (tecla A)": "Tap to open the analysis (key A)",
    "Mapa da pista": "Track map", "Telemetria comparada da curva": "Corner telemetry comparison",
    "Ex.: Max": "e.g. Max", "IDIOMA · LANGUAGE": "LANGUAGE · IDIOMA",
    "TORRE DE TEMPOS": "TIMING TOWER", "Tecla P ou toque na posição para abrir · Esc fecha": "Press P or tap the position to open · Esc closes",
    "Sem dados dos outros carros ainda.": "No data from the other cars yet.",
    "Classificação pelo melhor tempo": "Order by best lap time", "PILOTO": "DRIVER", "GAP": "GAP", "INT.": "INT.",
    "PNEU": "TYRE", "PARADAS": "STOPS", "VOCÊ": "YOU", "NO PIT": "IN PIT", "◀ parou": "◀ pitted", "FORA": "OUT",
    "+%d V": "+%d L",
    "Acerto novo: ": "New setup: ",
    "Reconhecimento de voz indisponível aqui. Use o Chrome ou o Edge no PC.": "Voice recognition isn't available here. Use Chrome or Edge on the PC.",
    "Ouvindo…": "Listening…", "Permita o microfone para falar com o engenheiro.": "Allow the microphone to talk to the engineer.",
    "Não ouvi nada. Aperte e fale de novo.": "Didn't hear anything. Press and talk again.",
    "Sem internet para reconhecer a voz.": "No internet connection for voice recognition.",
    "Nenhum microfone encontrado.": "No microphone found.", "O servidor do painel não respondeu.": "The dashboard server didn't respond.",
    "Falar com o engenheiro (tecla M ou UDP Action 11)": "Talk to the engineer (key M or UDP Action 11)",
    "Overlay F1 25": "F1 25 Overlay",
    "Não consegui usar o microfone. Confira se ele está conectado e liberado para apps em Privacidade > Microfone.":
      "Couldn't use the microphone. Check that it's connected and allowed for apps in Privacy > Microphone.",
    "Não consegui baixar o modelo de voz. Confira a internet e tente de novo.": "Couldn't download the voice model. Check your internet and try again.",
    "Entendendo…": "Understanding…",
    "Baixando o modelo de voz (só na primeira vez): %d%": "Downloading the voice model (first time only): %d%",
    "Não consegui ouvir: ": "Couldn't listen: ",

    "Painel aberto pela rede": "Dashboard opened over the network", "Fonte: ": "Source: ", "iniciando…": "starting…",
    "No celular ou tablet, na mesma rede, abra:": "On your phone or tablet, on the same network, open:", "Ligando…": "Turning on…",
    "Trocando a fonte… o painel reconecta sozinho.": "Switching the source… the dashboard reconnects by itself.",
    "Reiniciando o painel… ele reconecta sozinho.": "Restarting the dashboard… it reconnects by itself.",
    "Pergunta": "Question", "gravar": "record", "Controle conectado: ": "Controller connected: ",
    "Funcionam com o jogo em foco. No controle, segure %s e aperte o botão.": "They work with the game in focus. On the controller, hold %s and press the button.",
    "Nenhum controle XInput conectado (Xbox, ou PlayStation via Steam Input).": "No XInput controller connected (Xbox, or PlayStation via Steam Input).",
    "aperte Ctrl/Alt + tecla…": "press Ctrl/Alt + key…", "aperte o botão…": "press the button…",
    "Use Ctrl, Alt ou Shift junto, para não atrapalhar quando você digita.": "Use Ctrl, Alt or Shift with it, so it doesn't get in the way when you type.",
    "Jogo": "Game", "Demo corrida": "Demo race", "Demo Time Trial": "Demo Time Trial",
    "Abrir o menu": "Open the menu", "Falar com o engenheiro": "Talk to the engineer", "Torre de tempos": "Timing tower",
    "Análise da volta": "Lap analysis", "Overlay liga/desliga": "Overlay on/off", "Fechar as telas": "Close the screens",
    "Pneus": "Tyres", "Gaps": "Gaps", "Combustível e bateria": "Fuel and battery", "Onde estou perdendo": "Where am I losing time",
    "Clima e pit": "Weather and pit", "Repetir a última": "Repeat the last one", "Silêncio (só o essencial)": "Quiet (essentials only)",
    "Estratégia de pit": "Pit strategy", "Metas e treino": "Goals and practice", "Acerto do carro": "Car setup",
    "MENU": "MENU", "FONTE DA TELEMETRIA": "TELEMETRY SOURCE", "JOGO": "GAME", "DEMO CORRIDA": "DEMO RACE",
    "DEMO TIME TRIAL": "DEMO TIME TRIAL", "LIGAR E DESLIGAR": "ON AND OFF", "📱 Celular e tablet na rede": "📱 Phone and tablet on the network",
    "🖥 Overlay por cima do jogo": "🖥 Overlay on top of the game", "TELAS": "SCREENS", "Rádio e voz": "Radio and voice",
    "Controles e teclas": "Controls and keys", "PROGRAMA": "PROGRAM", "🌐 English": "🌐 English",
    "Tela cheia ou janela": "Full screen or window", "Sair do Painel F1 25": "Quit Painel F1 25",
    "CONTROLES E TECLAS": "CONTROLS AND KEYS", "RESTAURAR PADRÃO": "RESTORE DEFAULTS", "AÇÃO": "ACTION", "TECLA": "KEY",
    "CONTROLE": "CONTROLLER", "EVOLUÇÃO": "PROGRESS", "☰ MENU": "☰ MENU", "Menu (Esc)": "Menu (Esc)", "DELTA": "DELTA", "COMB.": "FUEL", "RÁDIO": "RADIO",
    "Acerto novo: a análise recomeça e aparece depois de 3 voltas lançadas.": "New setup: the analysis restarts and shows up after 3 flying laps."
  }/*FIM*/;

  const en = document.documentElement.lang === 'en';
  window.LANG_EN = en;
  window.LOCALE = en ? 'en-GB' : 'pt-BR';
  window.T = (s) => (en && Object.prototype.hasOwnProperty.call(EN, s) ? EN[s] : s);
  // numero com virgula decimal em portugues, ponto em ingles
  window.DEC = (x) => (en ? String(x) : String(x).replace('.', ','));

  if (!en) return;
  document.title = T(document.title);
  const andar = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = andar.nextNode(); n; n = andar.nextNode()) {
    const t = n.nodeValue.trim();
    if (t && Object.prototype.hasOwnProperty.call(EN, t)) n.nodeValue = n.nodeValue.replace(t, EN[t]);
  }
  for (const el of document.querySelectorAll('[title], [placeholder], [aria-label]')) {
    for (const a of ['title', 'placeholder', 'aria-label']) {
      const v = el.getAttribute(a);
      if (v && Object.prototype.hasOwnProperty.call(EN, v)) el.setAttribute(a, EN[v]);
    }
  }
})();
