// Pasta de dados (ao lado do .exe: o app e portatil) e ajustes do app (dados/app.json).
use std::{fs, path::PathBuf};

use serde::{Deserialize, Serialize};

/// dados/ ao lado do executavel. E a mesma pasta que o nucleo usa (historico, recordes, voz).
pub fn pasta_dados() -> PathBuf {
    let exe = std::env::current_exe().unwrap_or_default();
    let p = exe.parent().map(|p| p.join("dados")).unwrap_or_else(|| PathBuf::from("dados"));
    let _ = fs::create_dir_all(&p);
    p
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(default)]
pub struct Config {
    pub modo: String,
    pub overlay: bool,
    pub porta_udp: u16,
    pub porta_web: u16,
}

impl Default for Config {
    fn default() -> Self {
        Config { modo: "painel".into(), overlay: false, porta_udp: 20777, porta_web: 8025 }
    }
}

impl Config {
    fn caminho() -> PathBuf {
        pasta_dados().join("app.json")
    }

    pub fn carregar() -> Self {
        fs::read_to_string(Self::caminho()).ok().and_then(|s| serde_json::from_str(&s).ok()).unwrap_or_default()
    }

    pub fn salvar(&self) {
        if let Ok(s) = serde_json::to_string_pretty(self) {
            let _ = fs::write(Self::caminho(), s);
        }
    }
}

/// Idioma escolhido no painel (o nucleo guarda em dados/config.json). Sem ajuste: o do Windows.
pub fn idioma() -> String {
    let salvo = fs::read_to_string(pasta_dados().join("config.json"))
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v.get("idioma").and_then(|x| x.as_str()).map(String::from));
    salvo.unwrap_or_else(idioma_windows)
}

#[cfg(windows)]
fn idioma_windows() -> String {
    extern "system" {
        fn GetUserDefaultUILanguage() -> u16;
    }
    let lid = unsafe { GetUserDefaultUILanguage() };
    if lid & 0x3ff == 0x16 { "pt".into() } else { "en".into() }
}

#[cfg(not(windows))]
fn idioma_windows() -> String {
    "pt".into()
}
