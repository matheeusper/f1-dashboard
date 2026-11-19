// Compila a configuracao do Tauri e, se PAINELF1_NUCLEO apontar para o executavel do nucleo
// (o PainelF1.exe feito pelo PyInstaller), embute ele dentro do app: fica um .exe so.
use std::{env, fs, path::PathBuf};

fn main() {
    println!("cargo:rerun-if-env-changed=PAINELF1_NUCLEO");
    if let Ok(origem) = env::var("PAINELF1_NUCLEO") {
        let destino = PathBuf::from(env::var("OUT_DIR").unwrap()).join("nucleo.exe");
        fs::copy(&origem, &destino).expect("nao consegui copiar o nucleo (PAINELF1_NUCLEO)");
        println!("cargo:rerun-if-changed={origem}");
        println!("cargo:rustc-cfg=nucleo_embutido");
    }
    tauri_build::build()
}
