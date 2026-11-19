// Comandos sem o painel em foco: teclas globais (funcionam com o jogo em primeiro plano) e o
// controle de Xbox / XInput (lido direto, tambem sem foco). O mapa fica em dados/controles.json.
use std::{
    collections::HashMap,
    fs,
    str::FromStr,
    sync::{Mutex, OnceLock},
    thread,
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

use crate::{config, janelas, nucleo, Estado};

/// O que um botao ou tecla faz. "pergunta:N" = a mesma pergunta do botao UDP Action N.
fn executar(app: &AppHandle, acao: &str) {
    let app = app.clone();
    let acao = acao.to_string();
    thread::spawn(move || {
        let porta = app.state::<Estado>().nucleo.lock().unwrap().porta_web;
        let r = if let Some(n) = acao.strip_prefix("pergunta:") {
            match n.parse::<u8>() {
                Ok(n) => nucleo::post(porta, "/api/pergunta", serde_json::json!({ "acao": n })),
                Err(_) => Err(format!("pergunta invalida: {n}")),
            }
        } else if acao == "overlay" {
            alternar_overlay(&app);
            Ok(())
        } else if acao == "painel" {
            let url = app.state::<Estado>().nucleo.lock().unwrap().url();
            janelas::painel(&app, &url);
            Ok(())
        } else {
            // falar, torre, analise, ajustes, fechar: a pagina do painel reage
            nucleo::post(porta, "/api/comando", serde_json::json!({ "acao": acao }))
        };
        if let Err(e) = r {
            eprintln!("comando {acao}: {e}");
        }
    });
}

pub fn alternar_overlay(app: &AppHandle) -> bool {
    let st = app.state::<Estado>();
    let ligar = {
        let mut cfg = st.cfg.lock().unwrap();
        cfg.overlay = !cfg.overlay;
        cfg.salvar();
        cfg.overlay
    };
    let url = st.nucleo.lock().unwrap().url();
    janelas::overlay(app, &url, ligar);
    ligar
}

// ------------------------------------------------------------------ mapa (dados/controles.json)
#[derive(Serialize, Deserialize, Clone)]
#[serde(default)]
pub struct Controles {
    /// tecla -> acao. Ex.: "Ctrl+Alt+M": "falar"
    pub teclas: Vec<(String, String)>,
    /// botao que precisa estar apertado junto (evita disparar sem querer enquanto pilota)
    pub controle_modificador: String,
    /// botao -> acao (apertado junto com o modificador)
    pub controle: Vec<(String, String)>,
}

impl Default for Controles {
    fn default() -> Self {
        let p = |a: &str, b: &str| (a.to_string(), b.to_string());
        Controles {
            teclas: vec![
                p("Ctrl+Alt+M", "falar"),
                p("Ctrl+Alt+P", "torre"),
                p("Ctrl+Alt+A", "analise"),
                p("Ctrl+Alt+O", "overlay"),
                p("Ctrl+Alt+X", "fechar"),
                p("Ctrl+Alt+1", "pergunta:1"),
                p("Ctrl+Alt+2", "pergunta:2"),
                p("Ctrl+Alt+3", "pergunta:3"),
                p("Ctrl+Alt+4", "pergunta:4"),
                p("Ctrl+Alt+5", "pergunta:5"),
                p("Ctrl+Alt+6", "pergunta:6"),
                p("Ctrl+Alt+7", "pergunta:7"),
                p("Ctrl+Alt+8", "pergunta:8"),
                p("Ctrl+Alt+9", "pergunta:9"),
                p("Ctrl+Alt+0", "pergunta:10"),
            ],
            controle_modificador: "back".into(),
            controle: vec![
                p("a", "falar"),
                p("x", "pergunta:1"),
                p("b", "pergunta:2"),
                p("cima", "pergunta:3"),
                p("baixo", "pergunta:4"),
                p("esquerda", "pergunta:5"),
                p("direita", "pergunta:6"),
                p("y", "pergunta:8"),
                p("lb", "torre"),
                p("rb", "analise"),
                p("start", "overlay"),
                p("rs", "fechar"),
            ],
        }
    }
}

impl Controles {
    fn caminho() -> std::path::PathBuf {
        config::pasta_dados().join("controles.json")
    }

    fn carregar() -> Self {
        match fs::read_to_string(Self::caminho()).ok().and_then(|s| serde_json::from_str(&s).ok()) {
            Some(c) => c,
            None => {
                let c = Controles::default();
                if let Ok(s) = serde_json::to_string_pretty(&c) {
                    let _ = fs::write(Self::caminho(), s); // deixa o arquivo pronto para editar
                }
                c
            }
        }
    }
}

static CONTROLES: OnceLock<Controles> = OnceLock::new();
fn controles() -> &'static Controles {
    CONTROLES.get_or_init(Controles::carregar)
}

pub fn teclas_view() -> Vec<(String, String)> {
    controles().teclas.clone()
}

/// Texto curto para a tela de inicio: "conectado" ou None.
pub fn controle_view() -> Option<String> {
    CONTROLE_CONECTADO.lock().ok().and_then(|c| c.clone())
}

// ------------------------------------------------------------------ teclas globais
static MAPA_TECLAS: OnceLock<Mutex<HashMap<u32, String>>> = OnceLock::new();

pub fn plugin_teclas() -> tauri::plugin::TauriPlugin<tauri::Wry> {
    tauri_plugin_global_shortcut::Builder::new()
        .with_handler(|app, atalho, ev| {
            if ev.state() != ShortcutState::Pressed {
                return;
            }
            let acao = MAPA_TECLAS.get().and_then(|m| m.lock().ok()?.get(&atalho.id()).cloned());
            if let Some(a) = acao {
                executar(app, &a);
            }
        })
        .build()
}

pub fn registrar_teclas(app: &AppHandle) {
    let mapa = MAPA_TECLAS.get_or_init(|| Mutex::new(HashMap::new()));
    for (tecla, acao) in &controles().teclas {
        match Shortcut::from_str(tecla) {
            Ok(s) => {
                if let Err(e) = app.global_shortcut().register(s) {
                    eprintln!("tecla {tecla} indisponivel: {e}"); // outro programa ja usa
                } else {
                    mapa.lock().unwrap().insert(s.id(), acao.clone());
                }
            }
            Err(e) => eprintln!("tecla invalida {tecla}: {e}"),
        }
    }
}

// ------------------------------------------------------------------ controle (XInput)
static CONTROLE_CONECTADO: Mutex<Option<String>> = Mutex::new(None);

fn bit_do_botao(nome: &str) -> u16 {
    match nome.to_ascii_lowercase().as_str() {
        "cima" | "up" => 0x0001,
        "baixo" | "down" => 0x0002,
        "esquerda" | "left" => 0x0004,
        "direita" | "right" => 0x0008,
        "start" | "menu" => 0x0010,
        "back" | "view" | "select" => 0x0020,
        "ls" | "l3" => 0x0040,
        "rs" | "r3" => 0x0080,
        "lb" | "l1" => 0x0100,
        "rb" | "r1" => 0x0200,
        "a" | "cruz" => 0x1000,
        "b" | "bola" => 0x2000,
        "x" | "quadrado" => 0x4000,
        "y" | "triangulo" => 0x8000,
        _ => 0,
    }
}

#[cfg(windows)]
pub fn iniciar_controle(app: AppHandle) {
    use windows::Win32::UI::Input::XboxController::{XInputGetState, XINPUT_STATE};

    let c = controles();
    let modificador = bit_do_botao(&c.controle_modificador);
    let mapa: Vec<(u16, String)> =
        c.controle.iter().map(|(b, a)| (bit_do_botao(b), a.clone())).filter(|(b, _)| *b != 0).collect();
    thread::spawn(move || {
        let mut antes = [0u16; 4];
        let mut ligado = [false; 4];
        let mut proxima_busca = Instant::now();
        loop {
            // controles desconectados sao procurados so a cada 2 s (consultar slot vazio e lento)
            let buscar = Instant::now() >= proxima_busca;
            if buscar {
                proxima_busca = Instant::now() + Duration::from_secs(2);
            }
            for i in 0..4u32 {
                if !ligado[i as usize] && !buscar {
                    continue;
                }
                let mut s = XINPUT_STATE::default();
                let ok = unsafe { XInputGetState(i, &mut s) } == 0;
                ligado[i as usize] = ok;
                if !ok {
                    antes[i as usize] = 0;
                    continue;
                }
                let botoes = s.Gamepad.wButtons.0 as u16;
                let novos = botoes & !antes[i as usize];
                antes[i as usize] = botoes;
                if modificador == 0 || botoes & modificador != 0 {
                    for (bit, acao) in &mapa {
                        if novos & bit != 0 {
                            executar(&app, acao);
                        }
                    }
                }
            }
            let conectado = ligado.iter().any(|x| *x).then(|| "XInput".to_string());
            if let Ok(mut c) = CONTROLE_CONECTADO.lock() {
                *c = conectado;
            }
            thread::sleep(Duration::from_millis(15));
        }
    });
}

#[cfg(not(windows))]
pub fn iniciar_controle(_app: AppHandle) {}
