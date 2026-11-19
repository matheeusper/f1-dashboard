// Janelas do app: o painel (que e o programa: comeca na tela "Iniciando…" e depois mostra o
// painel do nucleo), o overlay transparente por cima do jogo e o icone na bandeja.
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, LogicalPosition, LogicalSize, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder,
};

use crate::{config, entrada};

// Todas as janelas usam o mesmo WebView2 com as mesmas opcoes: sem congelar quando o jogo cobre o
// painel e com o som liberado sem precisar clicar antes (o engenheiro fala sozinho).
#[cfg(not(debug_assertions))]
const ARGS_WEBVIEW: &str = "--autoplay-policy=no-user-gesture-required \
    --disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding --disable-background-timer-throttling";
// em desenvolvimento, com depuracao remota (porta 9223) para os testes automaticos
#[cfg(debug_assertions)]
const ARGS_WEBVIEW: &str = "--autoplay-policy=no-user-gesture-required \
    --disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding --disable-background-timer-throttling --remote-debugging-port=9223";

fn mostrar(w: &WebviewWindow) {
    let _ = w.unminimize();
    let _ = w.show();
    let _ = w.set_focus();
}

/// Cria o painel na tela "Iniciando…" (pagina local do app). Em tela cheia no monitor em pe, se
/// houver; senao uma janela 540x960.
pub fn criar_painel(app: &AppHandle) {
    if app.get_webview_window("painel").is_some() {
        return;
    }
    let mut b = WebviewWindowBuilder::new(app, "painel", WebviewUrl::App("index.html".into()))
        .title("Painel F1 25")
        .additional_browser_args(ARGS_WEBVIEW);
    let vertical = app
        .available_monitors()
        .unwrap_or_default()
        .into_iter()
        .find(|m| m.size().height > m.size().width);
    match vertical {
        Some(m) => {
            let s = m.scale_factor();
            let p = m.position();
            b = b.position(p.x as f64 / s, p.y as f64 / s).inner_size(m.size().width as f64 / s, m.size().height as f64 / s);
            if let Ok(w) = b.build() {
                let _ = w.set_fullscreen(true);
            }
        }
        None => {
            let _ = b.inner_size(540.0, 960.0).center().build();
        }
    }
}

pub fn mostrar_painel(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("painel") {
        mostrar(&w);
    } else {
        criar_painel(app);
    }
}

/// Leva o painel para a pagina do nucleo (se ainda estiver na tela "Iniciando…").
pub fn painel_no_nucleo(app: &AppHandle, url: &str) {
    if let Some(w) = app.get_webview_window("painel") {
        let atual = w.url().map(|u| u.to_string()).unwrap_or_default();
        if !atual.starts_with(url) {
            let _ = w.navigate(url.parse().expect("url do nucleo"));
        }
    }
}

/// Volta o painel para a tela "Iniciando…"/erro (o nucleo parou).
pub fn painel_iniciando(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("painel") {
        let atual = w.url().map(|u| u.to_string()).unwrap_or_default();
        if atual.starts_with("http://127.0.0.1") || atual.starts_with("http://localhost") {
            let _ = w.navigate("http://tauri.localhost/index.html".parse().unwrap()); // pagina local no Windows
        }
    }
}

pub fn alternar_tela_cheia(app: &AppHandle) -> bool {
    match app.get_webview_window("painel") {
        Some(w) => {
            let cheia = !w.is_fullscreen().unwrap_or(false);
            let _ = w.set_fullscreen(cheia);
            cheia
        }
        None => false,
    }
}

/// Overlay: faixa transparente no alto do monitor principal, sempre por cima e sem pegar clique
/// (o mouse e o teclado continuam indo para o jogo). Funciona com o jogo em tela cheia sem bordas.
pub fn overlay(app: &AppHandle, url: &str, ligar: bool) {
    if let Some(w) = app.get_webview_window("overlay") {
        if ligar {
            let _ = w.show();
        } else {
            let _ = w.hide();
        }
        return;
    }
    if !ligar {
        return;
    }
    let (x, y, larg) = match app.primary_monitor().ok().flatten() {
        Some(m) => {
            let s = m.scale_factor();
            let larg = (m.size().width as f64 / s).min(1280.0);
            (m.position().x as f64 / s + (m.size().width as f64 / s - larg) / 2.0, m.position().y as f64 / s, larg)
        }
        None => (0.0, 0.0, 1280.0),
    };
    let w = WebviewWindowBuilder::new(app, "overlay", WebviewUrl::External(format!("{url}/overlay").parse().unwrap()))
        .title("Painel F1 25 · overlay")
        .transparent(true)
        .decorations(false)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .focused(false)
        .resizable(false)
        .position(x, y)
        .inner_size(larg, 200.0)
        .additional_browser_args(ARGS_WEBVIEW)
        .build();
    if let Ok(w) = w {
        let _ = w.set_ignore_cursor_events(true);
        let _ = w.set_position(LogicalPosition::new(x, y));
        let _ = w.set_size(LogicalSize::new(larg, 200.0));
    }
}

fn textos() -> [&'static str; 3] {
    if config::idioma() == "en" {
        ["Show dashboard", "Overlay on/off", "Quit"]
    } else {
        ["Mostrar painel", "Overlay liga/desliga", "Sair"]
    }
}

fn menu(app: &AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let t = textos();
    Menu::with_items(
        app,
        &[
            &MenuItem::with_id(app, "painel", t[0], true, None::<&str>)?,
            &MenuItem::with_id(app, "overlay", t[1], true, None::<&str>)?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, "sair", t[2], true, None::<&str>)?,
        ],
    )
}

pub fn bandeja(app: &AppHandle) -> tauri::Result<()> {
    let icone = app.default_window_icon().cloned().expect("icone do app");
    TrayIconBuilder::with_id("bandeja")
        .icon(icone)
        .tooltip("Painel F1 25")
        .menu(&menu(app)?)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, ev| match ev.id().as_ref() {
            "painel" => mostrar_painel(app),
            "overlay" => {
                entrada::alternar_overlay(app);
            }
            "sair" => crate::encerrar(app),
            _ => {}
        })
        .on_tray_icon_event(|tray, ev| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = ev {
                mostrar_painel(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

/// Refaz o menu da bandeja no idioma atual.
pub fn bandeja_textos(app: &AppHandle) {
    if let (Some(t), Ok(m)) = (app.tray_by_id("bandeja"), menu(app)) {
        let _ = t.set_menu(Some(m));
    }
}
