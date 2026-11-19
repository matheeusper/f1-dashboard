# Painel F1 25: o programa (Rust + Tauri 2)

O `PainelF1.exe` é este app: um `.exe` só, portátil, com o núcleo Python (pasta `nucleo/`) embutido. Como usar está no [README principal](../README.md); aqui ficam as notas para quem mexe no código.

## Como funciona

- **Janela do painel:** abre a tela local `ui/index.html` ("Iniciando…") e, quando o núcleo responde, navega para a página que ele serve em `http://127.0.0.1:<porta>`. Se o núcleo não sobe (porta ocupada etc.), a mesma tela mostra o motivo, a escolha de fonte e "Tentar de novo".
- **IPC:** a página do painel vem do núcleo (origem remota). O Tauri só libera comandos para ela porque eles estão declarados no `build.rs` (`AppManifest`) e permitidos na `capabilities/default.json` (`remote.urls`). Comando novo precisa entrar nos dois lugares.
- **Comandos que criam janela** (overlay, tela cheia…) são `#[tauri::command(async)]`: no Windows, um comando síncrono que cria janela trava.
- **Núcleo:** em desenvolvimento roda pelo código com o uv (`uv run nucleo/server.py`). No `.exe` final vem embutido (`include_bytes!`, quando o `PAINELF1_NUCLEO` aponta para o `dist\PainelF1.exe` do PyInstaller) e é extraído para `%LOCALAPPDATA%\PainelF1\nucleo-<hash>.exe`. Um Job Object do Windows fecha o núcleo junto com o app.
- **Teclas globais:** `tauri-plugin-global-shortcut`. **Controle:** XInput lido direto (crate `windows`), funciona sem foco.
- **Ouvido:** `src/ouvido.rs` grava o microfone (cpal) e transcreve com o Whisper (whisper-rs, modelo `ggml-base`, baixado para `dados\modelos` na primeira vez). A página mostra o progresso por `estado_ouvido`.
- **Dados:** pasta `dados` ao lado do `.exe` (o núcleo recebe em `PAINELF1_DADOS`): histórico, ajustes, `app.json` (fonte, celular, overlay, portas) e `controles.json` (teclas e botões).

| Arquivo | O que faz |
|---|---|
| `src/main.rs` | Comandos chamados pela página, bandeja, início e fim do programa |
| `src/janelas.rs` | Janela do painel, overlay, tela cheia e bandeja |
| `src/nucleo.rs` | Sobe, confere e para o núcleo Python |
| `src/entrada.rs` | Teclas globais, controle XInput e o "gravar" da tela de controles |
| `src/ouvido.rs` | Microfone e Whisper |
| `src/config.rs` | `app.json` e o idioma |
| `ui/` | Tela "Iniciando…" e de erro |

## Compilar

Precisa do [Rust](https://rustup.rs), do Visual Studio Build Tools com C++ (inclui o CMake) e do [LLVM](https://github.com/llvm/llvm-project/releases) (o `libclang`, para compilar o Whisper). O `.cargo/config.toml` aponta o `LIBCLANG_PATH` para `C:\Program Files\LLVM\bin` e compila o whisper.cpp para qualquer processador com AVX2 (não só para o da sua máquina). O CMake precisa estar no PATH; o `build-app.ps1` já coloca.

```powershell
# desenvolvimento: roda o núcleo pelo código, com o uv (dados em app\target\debug\dados)
cd app
cargo run

# versão final: um .exe só, com o núcleo embutido
powershell -ExecutionPolicy Bypass -File build-app.ps1   # -> app\target\release\PainelF1.exe
```

A versão de desenvolvimento liga a depuração remota do WebView2 na porta 9223 e usa uma pasta de WebView2 separada, para não misturar com o programa instalado.

Teste da transcrição com um `.wav` (16 bits, mono, 16 kHz), usando o modelo já baixado em `target\debug\dados\modelos`:

```powershell
$env:PAINELF1_WAV = "pergunta.wav"; cargo test ouvido -- --ignored --nocapture
```

## Próximas etapas

1. Portar o núcleo de Python para Rust, módulo por módulo: pacotes UDP, estado, engenheiro, análise, estratégia, histórico. No fim fica sem Python e com um `.exe` menor.
2. As vozes neurais do engenheiro chamadas direto do Rust.
3. Atualização pelo próprio app (baixa a release nova e se substitui) e assinatura digital.
