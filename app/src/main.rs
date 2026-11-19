// Painel F1 25 (app nativo). Janela de inicio, painel, overlay e icone na bandeja; teclas
// globais e controle funcionando sem o painel em foco. A telemetria e o engenheiro rodam no
// nucleo Python (embutido no .exe), que o app inicia e com quem conversa por HTTP local.
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
    modo: String,
    rodando: bool,
    iniciando: bool,
    erro: Option<String>,
    url: String,
    lan: Option<String>,
    overlay: bool,
    idioma: String,
    teclas: Vec<(String, String)>,
    controle: Option<String>,
}

#[tauri::command]
fn estado(st: State<Estado>) -> EstadoView {
    let mut n = st.nucleo.lock().unwrap();
    let cfg = st.cfg.lock().unwrap();
    let rodando = n.rodando();
    EstadoView {
        modo: n.modo.clone(),
        rodando,
        iniciando: n.iniciando,
        erro: n.erro.clone(),
        url: n.url(),
        lan: if n.modo == "lan" && rodando { nucleo::ip_local().map(|ip| format!("http://{ip}:{}", n.porta_web)) } else { None },
        overlay: cfg.overlay,
        idioma: config::idioma(),
        teclas: entrada::teclas_view(),
        controle: entrada::controle_view(),
    }
}

/// Inicia (ou troca) o modo: painel, demo, tt (demo de Time Trial) ou lan (celular/tablet).
#[tauri::command(async)]
fn iniciar(app: AppHandle, modo: String) -> Result<(), String> {
    let st = app.state::<Estado>();
    {
        let mut cfg = st.cfg.lock().unwrap();
        cfg.modo = modo.clone();
        cfg.salvar();
    }
    st.nucleo.lock().unwrap().lancar(&modo)?;
    loop {
        std::thread::sleep(std::time::Duration::from_millis(300));
        if let Some(r) = st.nucleo.lock().unwrap().checar() {
            r?;
            break;
        }
    }
    let url = st.nucleo.lock().unwrap().url();
    janelas::painel(&app, &url);
    if st.cfg.lock().unwrap().overlay {
        janelas::overlay(&app, &url, true);
    }
    Ok(())
}

#[tauri::command]
fn abrir_painel(app: AppHandle) {
    let url = app.state::<Estado>().nucleo.lock().unwrap().url();
    janelas::painel(&app, &url);
}

#[tauri::command]
fn abrir_evolucao(app: AppHandle) {
    let url = app.state::<Estado>().nucleo.lock().unwrap().url();
    janelas::evolucao(&app, &url);
}

#[tauri::command]
fn alternar_overlay(app: AppHandle) -> bool {
    entrada::alternar_overlay(&app)
}

#[tauri::command(async)]
fn trocar_idioma(app: AppHandle, lang: String) -> Result<(), String> {
    let porta = app.state::<Estado>().nucleo.lock().unwrap().porta_web;
    nucleo::post(porta, "/api/config", serde_json::json!({ "idioma": lang }))?;
    janelas::bandeja_textos(&app);
    Ok(())
}

#[tauri::command]
fn sair(app: AppHandle) {
    app.state::<Estado>().nucleo.lock().unwrap().parar();
    app.exit(0);
}

fn main() {
    let cfg = config::Config::carregar();
    tauri::Builder::default()
        .plugin(entrada::plugin_teclas())
        .manage(Estado { nucleo: Mutex::new(nucleo::Nucleo::novo()), cfg: Mutex::new(cfg) })
        .invoke_handler(tauri::generate_handler![
            estado, iniciar, abrir_painel, abrir_evolucao, alternar_overlay, trocar_idioma, sair
        ])
        .setup(|app| {
            let h = app.handle().clone();
            janelas::bandeja(&h)?;
            janelas::inicio(&h);
            entrada::registrar_teclas(&h);
            entrada::iniciar_controle(h.clone());
            // abre direto no ultimo modo usado
            let modo = h.state::<Estado>().cfg.lock().unwrap().modo.clone();
            std::thread::spawn(move || {
                if let Err(e) = iniciar(h.clone(), modo) {
                    eprintln!("nucleo: {e}");
                }
            });
            Ok(())
        })
        .on_window_event(|janela, evento| {
            // fechar a janela de inicio so esconde: o painel continua rodando (icone na bandeja)
            if let tauri::WindowEvent::CloseRequested { api, .. } = evento {
                if janela.label() == "inicio" {
                    api.prevent_close();
                    let _ = janela.hide();
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
