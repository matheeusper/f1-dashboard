// Compila a configuracao do Tauri e, se PAINELF1_NUCLEO apontar para o executavel do nucleo
// (o PainelF1.exe feito pelo PyInstaller), embute ele dentro do app: fica um .exe so.
use std::{env, fs, path::PathBuf};

// Comandos que a janela do painel pode chamar. A pagina do painel vem do nucleo (127.0.0.1), e o
// Tauri so libera comandos para paginas remotas quando eles sao declarados aqui (e na capability).
const COMANDOS: &[&str] = &[
    "estado",
    "trocar_fonte",
    "compartilhar",
    "tentar_de_novo",
    "alternar_overlay",
    "tela_cheia",
    "idioma_mudou",
    "controles",
    "gravar_tecla",
    "gravar_botao",
    "restaurar_controles",
    "ouvir",
    "parar_ouvir",
    "abrir_privacidade_fala",
    "sair",
];

fn main() {
    println!("cargo:rerun-if-env-changed=PAINELF1_NUCLEO");
    if let Ok(origem) = env::var("PAINELF1_NUCLEO") {
        let destino = PathBuf::from(env::var("OUT_DIR").unwrap()).join("nucleo.exe");
        fs::copy(&origem, &destino).expect("nao consegui copiar o nucleo (PAINELF1_NUCLEO)");
        println!("cargo:rerun-if-changed={origem}");
        println!("cargo:rustc-cfg=nucleo_embutido");
    }
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(tauri_build::AppManifest::new().commands(COMANDOS)),
    )
    .expect("erro na configuracao do Tauri");
}
