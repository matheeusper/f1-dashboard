# Painel F1 25: telemetria e engenheiro de corrida com voz

**Português** · [English](README.en.md)

Painel em estilo cluster de carro para o **F1 25**, feito para um segundo monitor na vertical, um tablet ou o celular. Vem com um **engenheiro de corrida que fala com você pelo rádio, em português ou em inglês**:

- analisa cada curva, aprende os seus vícios e acompanha a sua evolução;
- faz a estratégia de pit;
- responde pelos botões do volante, pelo controle, por teclas e pela voz, mesmo com o jogo em primeiro plano.

<p align="center">
  <img src="docs/painel.jpg" alt="Painel no monitor vertical" width="32%">
  <img src="docs/analise.jpg" alt="Análise por curva com telemetria comparada" width="32%">
  <img src="docs/celular.jpg" alt="Layout compacto no celular deitado" width="32%">
</p>

> Projeto de fã, sem vínculo com a EA, a Codemasters ou a Formula 1. Usa só a telemetria UDP oficial que o jogo envia: não mexe no jogo e não usa mods.

## O que ele faz

- **Painel:**
  - RPM e LEDs de giro, marcha, velocidade, pedais, volante e força G;
  - DRS ou aero ativa;
  - tempos, setores e delta para a sua melhor volta;
  - ERS e combustível;
  - temperatura, pressão e desgaste dos pneus, freios, danos e unidade de potência.
- **Programa de verdade:** um `.exe` só, sem instalador. Abre direto no painel, e tudo fica no menu **☰**.
- **Comandos sem tirar o foco do jogo:** teclas globais (Ctrl+Alt+…) e controle de Xbox funcionam com o F1 25 em primeiro plano.
- **Overlay:** uma faixa transparente por cima do jogo, com posição, delta, rivais, ERS, combustível, o rádio do engenheiro e o minissetor de cada curva.
- **Engenheiro com voz natural:** fala só nas retas, chama você pelo nome, tem som de rádio de equipe e muda o tom conforme a situação.
- **Análise curva a curva:**
  - diz onde você perdeu tempo e por quê, por exemplo *"Na 3 você freou a 131 metros, o recorde freia a 90"*;
  - avisa antes da curva na volta seguinte;
  - tem gráfico de telemetria comparada com o seu recorde.
- **Memória:** recorde e volta ideal por pista, vícios que se repetem, resumo de cada sessão e a página **Evolução** com gráficos.
- **Corrida:** substitui o engenheiro do jogo. Usa os nomes dos pilotos e avisa de box box, limitador, pit dos rivais, undercut e overcut, safety car, punições, clima e zona de eliminação na classificação.
- **Estrategista de pit:** aprende quanto custa um pit em cada pista e prevê onde você volta à pista.
- **Torre de tempos:** o grid inteiro com gaps, intervalo, composto e idade dos pneus, paradas, última e melhor volta.
- **Pergunte pela voz:** aperte um botão e fale (*"como estão os pneus?"*, *"como estou na curva 3?"*): ele responde no rádio. No programa, a voz é entendida no seu PC, sem internet.
- **Time Trial:** modo treino de uma curva, metas do dia e conquistas.
- **Acerto:** detecta subesterço e sobresterço, sugere uma mudança por vez dentro dos limites do jogo e, depois que você muda, diz se melhorou.
- **Layouts:** monitor em pé, monitor ou tablet deitado, e celular (compacto, letras grandes).
- **Dois idiomas:** português e inglês, no painel, no programa e na voz do engenheiro.

## Instalação (Windows)

Não precisa instalar nada: é um arquivo só.

1. Na página de **[Releases](https://github.com/matheeusper/f1-dashboard/releases/latest)**, baixe o **`PainelF1.exe`** e coloque numa pasta sua, por exemplo `Documentos\PainelF1`.
2. **Configure o jogo** (uma vez só). No F1 25, vá em **Configurações → Telemetria**:

   | Opção | Valor |
   |---|---|
   | Telemetria UDP | Ligado |
   | Transmissão UDP | Desligado |
   | Endereço IP | 127.0.0.1 |
   | Porta UDP | 20777 |
   | Taxa de envio | 60 Hz |
   | Formato UDP | 2025 ou 2026 (os dois funcionam) |

3. Dê dois cliques em **`PainelF1.exe`**. O painel abre em tela cheia no monitor vertical, ou numa janela se você não tiver um.
4. Abra o jogo e entre na pista: o painel acende sozinho.

Na primeira vez, o Windows pode mostrar *"O Windows protegeu o computador"*, porque o programa não é assinado digitalmente. Clique em **Mais informações → Executar assim mesmo**.

Seus dados ficam na pasta `dados`, criada ao lado do `.exe`. Para atualizar, troque só o `PainelF1.exe` e mantenha essa pasta. Quem vem da versão 1.x pode colocar o `.exe` novo na mesma pasta: o histórico continua.

### O menu ☰

Clique no **☰** no canto do painel, aperte **Esc**, ou use **Ctrl+Alt+Espaço** de dentro do jogo.

| Item | O que faz |
|---|---|
| **Fonte da telemetria:** Jogo · Demo corrida · Demo Time Trial | Troca de onde vêm os dados. Os demos mostram tudo funcionando sem o jogo e gravam num histórico separado |
| **📱 Celular e tablet na rede** | Libera o painel na rede local e mostra o endereço para digitar no aparelho |
| **🖥 Overlay por cima do jogo** | Liga e desliga a faixa por cima do jogo |
| **Telas** | Torre de tempos, Análise da volta, Evolução, Rádio e voz, **Controles e teclas** |
| **Programa** | Idioma, tela cheia ou janela, e sair |

O programa também fica na bandeja do Windows, ao lado do relógio, com: mostrar o painel, overlay e sair. Fechar a janela do painel encerra o programa.

**Overlay:** funciona com o F1 25 em **tela cheia sem bordas** (borderless). Em tela cheia exclusiva, o Windows não deixa nenhuma janela ficar por cima.

## Comandos com o jogo em foco

**Teclado** (dá para trocar em ☰ → Controles e teclas → gravar):

| Tecla | O que faz |
|---|---|
| Ctrl+Alt+Espaço | Abre o menu ☰ |
| Ctrl+Alt+M | Falar com o engenheiro |
| Ctrl+Alt+1 … 0 | As perguntas dos botões UDP Action 1 a 10 |
| Ctrl+Alt+P | Torre de tempos |
| Ctrl+Alt+A | Análise da volta |
| Ctrl+Alt+O | Liga e desliga o overlay |
| Ctrl+Alt+X | Fecha torre, análise e ajustes |

**Controle** (XInput: Xbox, ou PlayStation pelo Steam Input/DS4Windows). **Segure View/Back** e aperte:

| Botão | O que faz |
|---|---|
| A | Falar com o engenheiro |
| X | Pneus |
| B | Gaps |
| Y | Estratégia de pit |
| ↑ / ↓ / ← / → | Combustível / Onde estou perdendo / Clima / Repetir |
| LB / RB | Torre / Análise |
| Start | Menu ☰ |
| RS (clique no analógico direito) | Fecha as telas |

Segurar View/Back junto existe para não disparar nada sem querer enquanto você pilota. Para trocar um botão: ☰ → Controles e teclas → gravar, e aperte o botão novo no controle.

**Volante:** os botões **UDP Action** do F1 25 também funcionam (veja [Botões do volante](#botões-do-volante)).

## Engenheiro de corrida

O engenheiro fala com você e mostra as mensagens na faixa **RÁDIO DO ENGENHEIRO**. Ele só fala nas retas, nunca na frenagem ou no meio da curva. Avisos urgentes, como dano, punição ou safety car, esperam no máximo 2 segundos.

**Voz e personalidade:** aperte **C**, ou abra ☰ → Rádio e voz, para escolher:
- **Idioma:** português ou inglês. O painel inteiro e o engenheiro mudam juntos.
- **Seu nome no rádio:** ele chama você pelo primeiro nome (*"Isso, Max! Recorde pessoal!"*). Por padrão, usa o nome do piloto que você escolheu no jogo, inclusive um piloto personalizado do Modo Carreira ou do My Team. Online, ou com a opção desligada nos Ajustes, vale o nome que você digitou.
- **A voz:** Antonio, Francisca ou Thalita, que são vozes neurais da Microsoft e soam humanas (em inglês: Ryan, Sonia, Andrew ou William). Ou a voz do Windows, que funciona sem internet.
- **Velocidade e volume.** O botão **▶ TESTAR VOZ** faz um rádio check.
- **Som de rádio de equipe:** bipes ao abrir e fechar a transmissão, voz filtrada e chiado regulável.

Ele muda o tom conforme a situação (animado num recorde, rápido num aviso urgente, calmo nas dicas) e varia as frases para não soar como gravação. As vozes naturais usam a internet. Sem conexão, o painel passa sozinho para a voz do Windows.

### Curva a curva

Na primeira volta limpa, o engenheiro mapeia as curvas da pista e numera em ordem: Curva 1, 2, 3… Em cada volta seguinte, ele compara cada curva com a sua referência e diz onde você perdeu tempo e por quê:
- freou cedo demais;
- freou tarde e passou do ponto;
- contornou mais devagar;
- acelerou tarde;
- travou a roda;
- patinou na saída.

Na volta seguinte, ele avisa **antes** da curva: *"Curva 3, freie a 90 metros."*

- **Pontos de frenagem em metros:** são medidos como as placas de 100/50 m, a partir do ponto em que o volante começa a virar na sua volta de referência.
- **Minissetores ao vivo:** ao sair de cada curva, o painel pisca o ganho ou a perda daquele trecho (**CURVA 4 +0,061**).
- **Telemetria comparada (tecla A):**
  - mapa da pista colorido por curva;
  - gráfico de velocidade, acelerador e freio da sua volta sobre os da referência;
  - os pontos de frenagem;
  - o tempo ganho ou perdido ao longo da curva.

### Memória e evolução

Tudo fica salvo em `dados/historico.sqlite3`:
- **Recorde por pista:** a telemetria da sua melhor volta vira a referência das próximas sessões.
- **Volta ideal:** a soma dos seus melhores trechos.
- **Vícios:** erros que se repetem na mesma curva. Ele lembra disso no começo da sessão e antes da curva.
- **Resumo da sessão:** compara com a sessão anterior e diz onde você evoluiu e o que treinar.
- **Página Evolução** (☰ → Evolução, tecla **E**, ou `http://127.0.0.1:8025/evolucao`): gráfico por sessão, tabela curva a curva com tendência e vícios, e conquistas.

### Corrida e classificação (no lugar do engenheiro do jogo)

- **Largada e posição:** volta de formação, luzes apagadas, *"Passou o Leclerc! P4"*, *"Você lidera!"*
- **Seu pit:**
  - *"Box, box"* na volta da estratégia, com a previsão de onde você volta à pista;
  - **"Limitador! Limitador!"**;
  - tempo da parada e pneus frios.
- **Estrategista:**
  - aprende quanto custa um pit em cada pista;
  - prevê a sua posição se parar agora (**PIT AGORA → P7** no rádio);
  - avisa *"Safety car! O pit custa só uns 12 segundos agora"*;
  - avisa de undercut e overcut;
  - compara os seus pneus com os dos rivais.
- **Rivais:** *"O Norris parou, colocou duros"*, ritmo (*"alcança em 4 voltas"*), DRS atrás, abandonos, volta mais rápida dos outros.
- **Regras e carro:**
  - combustível, com lift and coast nas curvas certas;
  - pneus e freios quentes ou frios;
  - desgaste dos pneus;
  - janela de pit, chuva e regra dos dois compostos;
  - limites de pista, punições, danos, furo, safety car e bandeiras.
- **Classificação:** tempo restante, **zona de eliminação** (*"P17, o corte é o Lindqvist, faltam 2 décimos"*), *"carro em volta rápida atrás"* e tráfego à frente.

**Para desligar o engenheiro do jogo:** baixe o volume do rádio do engenheiro no menu de **Áudio** do F1 25. O menu MFD do volante continua funcionando normalmente.

### Botões do volante

O F1 25 tem os botões **"UDP Action 1" a "UDP Action 12"**. Mapeie-os em **Configurações → Controles** (costumam ficar no fim da lista) e o engenheiro responde na hora:

| Botão | Você pergunta | Ele responde, por exemplo |
|---|---|---|
| UDP Action 1 | Pneus | "Pneus médios com 7 voltas. Desgaste de 18%, o pior é o dianteiro esquerdo. Chegam a 70% em umas 12 voltas." |
| UDP Action 2 | Gaps | "P4. Norris, P3, está a 1,2 segundo, você tira 2 décimos por volta." |
| UDP Action 3 | Combustível e bateria | "Combustível mais 0,4 volta, mistura padrão. Bateria em 64%." |
| UDP Action 4 | Onde estou perdendo | "Na última volta você perdeu mais na 3, 4 décimos: freou a 131 m, o recorde freia a 90." |
| UDP Action 5 | Clima e pit | "Pista a 34 graus. Chuva de 65% em 10 minutos. Janela de pit entre as voltas 6 e 8." |
| UDP Action 6 | Repetir | Repete a última mensagem. |
| UDP Action 7 | Silêncio | Liga ou desliga o modo "só o essencial". |
| UDP Action 8 | Estratégia de pit | "O pit aqui custa uns 21 segundos. Se parar agora, volta em P5, atrás do Norris." |
| UDP Action 9 | Metas e treino | Progresso de cada meta do Time Trial. |
| UDP Action 10 | Acerto do carro | "Subesterço no meio das curvas 2, 5 e 9. Sugestão: asa dianteira de 28 para 29 (mais asa)…" |
| UDP Action 11 | Falar com o engenheiro | Ele ouve a sua pergunta. |

No painel, as teclas **1 a 9** e **0** (que vale como 10) fazem as mesmas perguntas.

### Falar com o engenheiro

Aperte **UDP Action 11** no volante, **Ctrl+Alt+M**, **View + A** no controle, a tecla **M** ou o **🎤** no rádio do painel. Você ouve um bipe, o rádio fica verde com *"Ouvindo…"*, e é só falar. Ele para de ouvir sozinho quando você fica em silêncio. Por exemplo:

- *"Como estão os pneus?"*, *"qual o gap pro da frente?"*, *"quanto de combustível?"*, *"vai chover?"*
- *"Onde estou perdendo tempo?"*, *"qual a estratégia de pit?"*, *"como está o acerto?"*
- *"Como estou na curva 3?"*: perda, motivo e onde a referência freia naquela curva na última volta.
- *"Repete"*, *"fica quieto"*.

No programa, quem ouve é o **Whisper**, rodando no seu PC: funciona offline e sem conta. Na primeira vez, ele baixa o modelo de voz (~150 MB) para `dados\modelos`, e o rádio mostra o progresso. Com fone, ele não ouve o próprio engenheiro.

Abrindo o painel pelo Chrome ou pelo Edge (rodando pelo código), vale o reconhecimento de voz do navegador, que precisa de internet. No celular pela rede local não funciona, porque o navegador só libera o microfone em conexão segura.

### Modo treino com metas (só no Time Trial)

- **Metas do dia:**
  - um tempo para bater;
  - *"5 voltas seguidas sem travar"*;
  - constância;
  - o seu vício.

  Meta cumprida vira **conquista** na página Evolução.
- **Treinar uma curva:** selecione a curva na análise (**A**) e aperte **T**. A cada volta ele diz quanto você ficou do seu melhor trecho, onde freou contra o alvo e a variação nas últimas 5 voltas.

### Análise do acerto

O engenheiro mede o equilíbrio do carro na entrada, no meio e na saída de cada curva, pela deriva dos pneus dianteiros contra a dos traseiros. Também considera as patinadas e a temperatura dos pneus, e só aponta o que se repete em 3 voltas ou mais.

**Sugestões:** uma mudança por vez, a do problema que aparece em mais curvas.
- Só sugere quando a maioria das curvas concorda: se umas pedem uma coisa e outras o contrário, ele avisa que o equilíbrio está misto e não mexe no acerto.
- Respeita os limites do jogo (balanço de freio 50–70%, asas 0–50, diferencial 10–100%, barras 1–21): nunca sugere passar do limite.
- Em classificação, sprint e corrida (parc fermé), só sugere o que muda pelo MFD: balanço de freio e diferencial no acelerador.

| O que ele vê | O que sugere primeiro |
|---|---|
| Subesterço na entrada | Balanço de freio mais para trás (depois, diferencial sem acelerador mais aberto) |
| Sobresterço na entrada | Balanço de freio mais para frente (depois, diferencial sem acelerador mais fechado) |
| Subesterço no meio das curvas rápidas | Mais asa dianteira (ou menos asa traseira) |
| Sobresterço no meio das curvas rápidas | Mais asa traseira (ou menos asa dianteira) |
| Subesterço no meio das curvas lentas | Barra estabilizadora dianteira mais macia (ou traseira mais dura) |
| Sobresterço no meio das curvas lentas | Barra estabilizadora traseira mais macia (ou dianteira mais dura) |
| Sobresterço ou patinada na saída | Diferencial no acelerador mais aberto |

**Antes e depois:** quando você muda o acerto, na garagem ou pelo MFD, ele descarta as voltas antigas, recomeça a contagem e, depois de 3 voltas, compara com o acerto anterior. Diz se melhorou, piorou ou passou do ponto, e com qual valor voltar. Por exemplo: *"Asa dianteira 28→29: subesterço no meio das curvas rápidas de 4 para 1 curvas, volta 0,13 s mais rápida. Melhorou: mantém."* O que piorou não é sugerido de novo.

## Celular e tablet

1. No programa, ligue **☰ → 📱 Celular e tablet na rede**. Aparece o endereço para digitar no aparelho, por exemplo `http://192.168.0.10:8025`.
2. O celular precisa estar na mesma rede do PC.
3. Na primeira vez, libere o Painel F1 25 no firewall do Windows: marque também **Redes públicas** se a sua rede estiver como pública.

- **Layouts:** o painel escolhe o layout pela tela. No celular ele fica compacto, com tudo grande, deitado ou em pé.
- **Tela cheia:** toque na barra de cima.
- **Forçar um layout:** coloque `?modo=celular` ou `?modo=monitor` no fim do endereço.
- **Voz:** deixe **VOZ: DESLIGADA** no celular para o engenheiro não falar em dois aparelhos.

## Atalhos do painel

| Tecla | O que faz |
|---|---|
| **Esc** | Fecha a tela aberta. Sem nenhuma aberta, abre o menu ☰ |
| **A** | Análise da última volta: mapa, telemetria comparada, metas e acerto. Use **← →** ou clique para trocar de curva |
| **P** | Torre de tempos: o grid inteiro (ou toque no P da posição) |
| **M** | Falar com o engenheiro (ou o 🎤 no rádio) |
| **E** | Página Evolução |
| **C** | Ajustes do rádio: idioma, nome, voz, velocidade, volume e som de rádio |
| **V** | Voz: tudo → só importante → desligada |
| **1 a 9, 0** | Perguntas ao engenheiro (as mesmas dos botões do volante) |
| **T** | Time Trial: treinar a curva selecionada |

## Problemas comuns

- **"Aguardando o F1 25" com o jogo aberto:** confira o IP 127.0.0.1, a porta 20777 e se a telemetria UDP está ligada. Você precisa estar na pista: nos menus, o jogo não envia dados.
- **"A porta UDP 20777 já está em uso":** outro app de telemetria (SimHub, Crew Chief…) está usando a porta. Feche o outro app e clique em **Tentar de novo**.
- **Jogo no PS5/Xbox ou em outro PC:** ligue **☰ → Celular e tablet na rede** (ele passa a aceitar telemetria da rede) e coloque no jogo o IP deste PC (veja com `ipconfig`).
- **O engenheiro não fala:** confira se o rádio não está em "VOZ: DESLIGADA" (tecla V).
- **As teclas Ctrl+Alt não funcionam no jogo:** outro programa pode estar usando a mesma combinação. Troque em ☰ → Controles e teclas → gravar.
- **Começar o histórico do zero:** apague a pasta `dados` com o programa fechado.

**Limitações conhecidas:**
- O jogo não informa o nome das curvas. A numeração é do engenheiro, na ordem da pista, e se mantém igual entre sessões.
- No online, a comparação com rivais depende de eles deixarem a telemetria pública.

## Para desenvolvedores

| Pasta | O que tem |
|---|---|
| `app/` | O programa (Rust + Tauri 2): janela do painel, menu ☰, overlay, bandeja, teclas globais, controle XInput e o ouvido com Whisper. Veja o [app/README.md](app/README.md) |
| `nucleo/` | O núcleo em Python: recebe a telemetria UDP, roda o engenheiro e serve a página por HTTP/SSE. O app embute ele |
| `web/` | O painel, a página Evolução e o overlay (HTML, CSS e JS puro, sem build). O `web/i18n.js` traduz as páginas |
| `tools/` | `checar_traducao.py` (confere as traduções) e `gerar_icone.py` (gera os ícones) |
| `docs/` | Imagens do README |

| Arquivo do núcleo | O que faz |
|---|---|
| `server.py` | Servidor: recebe a telemetria UDP e entrega o estado à página por SSE |
| `f1_packets.py` | Decodifica os pacotes do F1 25 (formatos 2025 e 2026) |
| `engenheiro.py` | O engenheiro: análise por volta, regras, mensagens, vícios, resumo |
| `analise.py` | Detecta as curvas e compara voltas curva a curva |
| `corrida.py` | Avisos de corrida e classificação (posição, pit, rivais, eventos) |
| `estrategia.py` | Estrategista de pit |
| `treino.py` | Modo treino e metas do Time Trial |
| `acerto.py` | Análise do acerto do carro |
| `historico.py` | Histórico em SQLite e dados da página Evolução |
| `voz.py` | Voz neural (edge-tts) e ajustes |
| `ouvido.py` | Entende a pergunta falada (palavras-chave) e escolhe a resposta |
| `idioma.py`, `textos_en.py` | Idioma e a tradução inglesa do engenheiro e do servidor |
| `simulador.py` | Gera telemetria falsa no formato do jogo, para testes |
| `caminhos.py` | Onde ficam os arquivos, rodando pelo código ou como executável |

O núcleo usa só a biblioteca padrão do Python, mais o [`edge-tts`](https://pypi.org/project/edge-tts/) para a voz. Para rodar pelo código, instale o [uv](https://docs.astral.sh/uv/), que baixa o Python certo sozinho:

```bash
cd app && cargo run                                   # o programa, rodando o núcleo pelo código
uv run nucleo/server.py --demo --abrir                # só o núcleo, com o painel no Chrome/Edge
uv run nucleo/simulador.py --porta 20777              # só o simulador, enviando para um núcleo já aberto
uv run tools/checar_traducao.py                       # confere se todo texto tem tradução em inglês
powershell -ExecutionPolicy Bypass -File build-app.ps1  # gera o app\target\release\PainelF1.exe
```

**Opções do núcleo** (`uv run nucleo/server.py [opções]`; no Linux e no macOS dá para usar o painel assim, pelo navegador):

| Opção | O que faz |
|---|---|
| `--abrir` | Abre o painel no Chrome ou Edge, em tela cheia no monitor vertical, se houver |
| `--demo` | Telemetria simulada, sem o jogo |
| `--time-trial` | Com `--demo`: simula um Time Trial |
| `--formato 2026` | Com `--demo`: usa o formato UDP 2026 |
| `--lan` | Aceita conexões de outros aparelhos da rede (celular, tablet, console) |
| `--porta-udp N` | Porta da telemetria (padrão 20777) |
| `--porta-web N` | Porta da página (padrão 8025) |
| `--historico ARQ` | Usa outro arquivo de histórico |

**Traduções:** os textos ficam escritos em português dentro de `tx("...")` (ou `N_("...")` em listas do módulo) no Python e de `T('...')` nas páginas. As versões em inglês ficam em `nucleo/textos_en.py` e `web/i18n.js`, com o texto em português como chave. O `tools/checar_traducao.py` aponta o que faltar.

**Executável:** o `build-app.ps1` compila o núcleo com o PyInstaller (`build.ps1`, que gera o `dist\PainelF1.exe`) e depois o app em Rust, com esse núcleo embutido. O resultado é um `.exe` só. O mesmo build roda no GitHub Actions (`.github/workflows/executavel.yml`): a cada release publicada, o `.exe` é compilado num Windows e anexado à release.

A especificação UDP do F1 25 está nos fóruns oficiais da EA (*Data Output from F1 25*).

## Licença

[MIT](LICENSE). Use, modifique e compartilhe à vontade.
