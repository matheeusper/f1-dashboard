// Painel F1 25 (app nativo). O proprio painel e o programa: abre direto, e tudo (fonte da
// telemetria, celular, overlay, controles, sair) fica no menu ☰ do painel. Teclas globais e o
// controle funcionam sem o painel em foco. A telemetria e o engenheiro rodam no nucleo Python
// (embutido no .exe), que o app inicia e com quem conversa por HTTP local.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod config;
mod entrada;
mod janelas;
mod nucleo;

use std::sync::Mutex;

use serde::Serialize;
use tauri::{AppHandle, Manager, State};

pub struct Estado {
    pub nucleo: Mutex<nucleo::Nucleo>,
    pub cfg: Mutex<config::Config>,
}

#[derive(Serialize)]
struct EstadoView {
    fonte: String,
    compartilhar: bool,
    overlay: bool,
    rodando: bool,
    iniciando: bool,
    erro: Option<String>,
    url: String,
    lan: Option<String>,
    idioma: String,
    controle: Option<String>,
    tela_cheia: bool,
}

#[tauri::command]
fn estado(app: AppHandle, st: State<Estado>) -> EstadoView {
    let mut n = st.nucleo.lock().unwrap();
    let cfg = st.cfg.lock().unwrap();
    let rodando = n.rodando() && !n.iniciando;
    EstadoView {
        fonte: n.fonte.clone(),
        compartilhar: n.compartilhar,
        overlay: cfg.overlay,
        rodando,
        iniciando: n.iniciando,
        erro: n.erro.clone(),
        url: n.url(),
        lan: if n.compartilhar && rodando { nucleo::ip_local().map(|ip| format!("http://{ip}:{}", n.porta_web)) } else { None },
        idioma: config::idioma(),
        controle: entrada::controle_view(),
        tela_cheia: app.get_webview_window("painel").and_then(|w| w.is_fullscreen().ok()).unwrap_or(false),
    }
}

/// (Re)inicia o nucleo com a fonte e o compartilhamento atuais e leva o painel para ele.
fn subir_nucleo(app: &AppHandle) -> Result<(), String> {
    let st = app.state::<Estado>();
    let (fonte, compartilhar) = {
        let cfg = st.cfg.lock().unwrap();
        (cfg.fonte.clone(), cfg.compartilhar)
    };
    st.nucleo.lock().unwrap().lancar(&fonte, compartilhar)?;
    loop {
        std::thread::sleep(std::time::Duration::from_millis(300));
        let r = st.nucleo.lock().unwrap().checar();
        if let Some(r) = r {
            if r.is_err() {
                janelas::painel_iniciando(app); // mostra o erro na tela "Iniciando…"
            }
            r?;
            break;
        }
    }
    let url = st.nucleo.lock().unwrap().url();
    janelas::painel_no_nucleo(app, &url);
    if st.cfg.lock().unwrap().overlay {
        janelas::overlay(app, &url, true);
    }
    Ok(())
}

/// Fonte da telemetria: "jogo", "demo" ou "tt".
#[tauri::command(async)]
fn trocar_fonte(app: AppHandle, fonte: String) -> Result<(), String> {
    if !matches!(fonte.as_str(), "jogo" | "demo" | "tt") {
        return Err("fonte invalida".into());
    }
    {
        let st = app.state::<Estado>();
        let mut cfg = st.cfg.lock().unwrap();
        cfg.fonte = fonte;
        cfg.salvar();
    }
    subir_nucleo(&app)
}

/// Libera (ou nao) o painel na rede local, para o celular e o tablet.
#[tauri::command(async)]
fn compartilhar(app: AppHandle, ligar: bool) -> Result<(), String> {
    {
        let st = app.state::<Estado>();
        let mut cfg = st.cfg.lock().unwrap();
        cfg.compartilhar = ligar;
        cfg.salvar();
    }
    subir_nucleo(&app)
}

#[tauri::command(async)]
fn tentar_de_novo(app: AppHandle) -> Result<(), String> {
    subir_nucleo(&app)
}

// async: criar janela num comando sincrono trava no Windows (ele roda na thread principal)
#[tauri::command(async)]
fn alternar_overlay(app: AppHandle) -> bool {
    entrada::alternar_overlay(&app)
}

#[tauri::command(async)]
fn tela_cheia(app: AppHandle) -> bool {
    janelas::alternar_tela_cheia(&app)
}

#[tauri::command(async)]
fn idioma_mudou(app: AppHandle) {
    janelas::bandeja_textos(&app);
}

#[tauri::command]
fn controles() -> entrada::Controles {
    entrada::controles()
}

#[tauri::command]
fn gravar_tecla(app: AppHandle, acao: String, tecla: String) -> Result<(), String> {
    entrada::definir_tecla(&app, &acao, &tecla)
}

/// Espera o proximo botao do controle (ate 8 s) e grava para a acao. Devolve o nome do botao.
#[tauri::command(async)]
fn gravar_botao(app: AppHandle, acao: String) -> Result<String, String> {
    let botao = entrada::esperar_botao()?;
    entrada::definir_botao(&app, &acao, &botao);
    Ok(botao)
}

#[tauri::command]
fn restaurar_controles(app: AppHandle) {
    entrada::restaurar(&app);
}

#[tauri::command]
fn sair(app: AppHandle) {
    encerrar(&app);
}

pub fn encerrar(app: &AppHandle) {
    app.state::<Estado>().nucleo.lock().unwrap().parar();
    app.exit(0);
}

fn main() {
    let cfg = config::Config::carregar();
    tauri::Builder::default()
        .plugin(entrada::plugin_teclas())
        .manage(Estado { nucleo: Mutex::new(nucleo::Nucleo::novo()), cfg: Mutex::new(cfg) })
        .invoke_handler(tauri::generate_handler![
            estado,
            trocar_fonte,
            compartilhar,
            tentar_de_novo,
            alternar_overlay,
            tela_cheia,
            idioma_mudou,
            controles,
            gravar_tecla,
            gravar_botao,
            restaurar_controles,
            sair
        ])
        .setup(|app| {
            let h = app.handle().clone();
            janelas::bandeja(&h)?;
            janelas::criar_painel(&h);
            entrada::registrar_teclas(&h);
            entrada::iniciar_controle(h.clone());
            std::thread::spawn(move || {
                if let Err(e) = subir_nucleo(&h) {
                    eprintln!("nucleo: {e}");
                }
            });
            Ok(())
        })
        .on_window_event(|janela, evento| {
            // o painel e o programa: fechar a janela dele encerra tudo
            if let tauri::WindowEvent::CloseRequested { .. } = evento {
                if janela.label() == "painel" {
                    encerrar(janela.app_handle());
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("erro ao iniciar o app")
        .run(|app, evento| {
            if let tauri::RunEvent::Exit = evento {
                app.state::<Estado>().nucleo.lock().unwrap().parar();
            }
        });
}
