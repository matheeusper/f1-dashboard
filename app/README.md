# Painel F1 25: app nativo (em desenvolvimento)

Versão nativa do Painel F1 25, feita com **Rust + Tauri 2**. É um `.exe` só, portátil (sem instalador). **O próprio painel é o programa**:

- abre direto o **painel**: em tela cheia no monitor vertical, ou numa janela 540×960 se não houver um. Enquanto o núcleo sobe, aparece "Iniciando…"; se der erro (porta ocupada etc.), a mesma tela mostra o motivo e "Tentar de novo";
- tudo fica no **menu ☰** do painel (botão no topo, **Esc** ou Ctrl+Alt+Espaço):
  - fonte da telemetria (Jogo, Demo corrida, Demo Time Trial);
  - chaves de **celular e tablet** e **overlay**;
  - telas (torre, análise, evolução, rádio e voz, **controles e teclas** com "gravar");
  - idioma, tela cheia ou janela, e sair;
- o **overlay** é uma faixa transparente por cima do jogo;
- **ícone na bandeja**: mostrar o painel, overlay e sair. Fechar a janela do painel encerra o programa;
- recebe comandos **sem o painel em foco**, com o F1 25 em primeiro plano:
  - **teclas globais** (Ctrl+Alt+…);
  - **controle de Xbox / XInput**, lido direto;
- roda o núcleo Python (telemetria e engenheiro) embutido e conversa com ele por HTTP local, então o celular e o tablet continuam funcionando pela rede, igual antes.

Os dados ficam na pasta `dados` ao lado do `.exe`: histórico, ajustes, `app.json` (fonte, celular e overlay) e `controles.json` (teclas e botões). Pelo celular, o mesmo painel abre pela rede, e o ☰ mostra só torre, análise, evolução, rádio e idioma.

## Comandos

**Teclado** (funcionam com o jogo em foco; dá para trocar em ☰ → Controles e teclas → gravar):

| Tecla | O que faz |
|---|---|
| Ctrl+Alt+Espaço | Abre o menu ☰ |
| Ctrl+Alt+M | Falar com o engenheiro |
| Ctrl+Alt+1 … 0 | As perguntas dos botões UDP Action 1 a 10 |
| Ctrl+Alt+P | Torre de tempos |
| Ctrl+Alt+A | Análise da volta |
| Ctrl+Alt+O | Liga e desliga o overlay |
| Ctrl+Alt+X | Fecha torre, análise e ajustes |

**Controle** (XInput: Xbox, ou PlayStation via Steam Input/DS4Windows). **Segure View/Back** e aperte:

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

O botão segurado junto (View/Back) existe para não disparar nada sem querer enquanto você pilota. Para trocar um botão: ☰ → Controles e teclas → gravar, e aperte o botão novo no controle.

**Overlay:** funciona com o F1 25 em **tela cheia sem bordas** (borderless). Em tela cheia exclusiva o Windows não deixa nenhuma janela ficar por cima, e contornar isso exigiria mexer no jogo, o que o anti-cheat pune.

## Compilar

Precisa do [Rust](https://rustup.rs) e do Visual Studio Build Tools com C++.

```powershell
# desenvolvimento: roda o núcleo pelo código, com o uv (dados em app\target\debug\dados)
cd app
cargo run

# versão final: um .exe só, com o núcleo embutido
powershell -ExecutionPolicy Bypass -File build-app.ps1   # -> app\target\release\PainelF1.exe
```

## Próximas etapas

1. Portar o núcleo de Python para Rust, módulo por módulo: pacotes UDP, estado, engenheiro, análise, estratégia, histórico. No fim fica sem Python e com um `.exe` menor.
2. Voz nativa: microfone com Whisper (offline) e as vozes neurais chamadas direto do Rust.
3. Atualização pelo próprio app (baixa a release nova e se substitui) e assinatura digital.
