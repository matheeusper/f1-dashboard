// Ouvir a pergunta pelo microfone com o reconhecimento de fala do proprio Windows
// (Windows.Media.SpeechRecognition). Dentro da janela do app (WebView2) o reconhecimento do
// Chrome nao existe, entao quem ouve e o app; a pagina so mostra "Ouvindo…" e manda o texto.
//
// Erros voltam como codigos curtos que a pagina traduz: "privacidade" (reconhecimento de fala
// online desligado no Windows), "microfone", "nada" (nao ouviu nada), "idioma", "outro: ...".

#[cfg(windows)]
mod win {
    use std::sync::Mutex;
    use windows::{
        core::HSTRING,
        Foundation::{TimeSpan, TypedEventHandler},
        Globalization::Language,
        Media::SpeechRecognition::{
            SpeechRecognitionHypothesisGeneratedEventArgs, SpeechRecognitionResultStatus, SpeechRecognizer,
        },
        Win32::System::WinRT::{RoInitialize, RO_INIT_MULTITHREADED},
    };

    // o reconhecedor em uso (para "parar" quando aperta de novo)
    static ATUAL: Mutex<Option<SpeechRecognizer>> = Mutex::new(None);
    // o que o Windows ja entendeu enquanto voce falava (usado se o final vier com erro)
    static PARCIAL: Mutex<String> = Mutex::new(String::new());

    const PRIVACIDADE: i32 = 0x8004_5509u32 as i32; // SPERR_SPEECH_PRIVACY_POLICY_NOT_ACCEPTED
    const SEM_MICROFONE: [i32; 2] = [0x8004_5303u32 as i32, 0x8007_0005u32 as i32]; // sem dispositivo / acesso negado

    fn ms(s: f64) -> TimeSpan {
        TimeSpan { Duration: (s * 10_000_000.0) as i64 } // unidades de 100 ns
    }

    fn codigo(e: windows::core::Error) -> String {
        let h = e.code().0;
        if h == PRIVACIDADE {
            "privacidade".into()
        } else if SEM_MICROFONE.contains(&h) {
            "microfone".into()
        } else {
            format!("outro: {}", e.message())
        }
    }

    /// Idioma do reconhecedor: o do painel, se o Windows tiver; senao o padrao do Windows.
    fn reconhecedor(idioma: &str) -> windows::core::Result<SpeechRecognizer> {
        let prefixo = if idioma == "en" { "en" } else { "pt" };
        if let Ok(langs) = SpeechRecognizer::SupportedTopicLanguages() {
            for l in langs {
                if l.LanguageTag()?.to_string().to_ascii_lowercase().starts_with(prefixo) {
                    return SpeechRecognizer::Create(&l);
                }
            }
        }
        let _ = Language::CreateLanguage(&HSTRING::from("pt-BR")); // so para garantir o tipo carregado
        SpeechRecognizer::new()
    }

    pub fn ouvir(idioma: &str) -> Result<String, String> {
        unsafe {
            let _ = RoInitialize(RO_INIT_MULTITHREADED); // ja inicializado: tudo bem
        }
        let rec = reconhecedor(idioma).map_err(codigo)?;
        // so o tempo para comecar a falar; o resto fica no padrao do Windows (mexer nele dava status 6)
        let _ = rec.Timeouts().and_then(|t| t.SetInitialSilenceTimeout(ms(5.0)));
        PARCIAL.lock().unwrap().clear();
        let _ = rec.HypothesisGenerated(&TypedEventHandler::<SpeechRecognizer, SpeechRecognitionHypothesisGeneratedEventArgs>::new(
            |_, args| {
                if let Some(a) = args.as_ref() {
                    if let Ok(t) = a.Hypothesis().and_then(|h| h.Text()) {
                        *PARCIAL.lock().unwrap() = t.to_string();
                    }
                }
                Ok(())
            },
        ));
        let comp = rec.CompileConstraintsAsync().map_err(codigo)?.get().map_err(codigo)?;
        if comp.Status().map_err(codigo)? != SpeechRecognitionResultStatus::Success {
            return Err(status(comp.Status().unwrap_or(SpeechRecognitionResultStatus::Unknown)));
        }
        *ATUAL.lock().unwrap() = Some(rec.clone());
        let r = rec.RecognizeAsync().map_err(codigo).and_then(|op| op.get().map_err(codigo));
        *ATUAL.lock().unwrap() = None;
        let parcial = PARCIAL.lock().unwrap().clone();
        let r = match r {
            Ok(r) => r,
            Err(e) if !parcial.trim().is_empty() => {
                eprintln!("ouvir: {e}; usando o que ja tinha entendido");
                return Ok(parcial);
            }
            Err(e) => return Err(e),
        };
        let st = r.Status().map_err(codigo)?;
        if st != SpeechRecognitionResultStatus::Success {
            if !parcial.trim().is_empty() {
                return Ok(parcial); // o final falhou, mas ele ja tinha entendido a pergunta
            }
            return Err(status(st));
        }
        let mut texto = r.Text().map_err(codigo)?.to_string();
        if texto.trim().is_empty() {
            texto = parcial;
        }
        if texto.trim().is_empty() {
            return Err("nada".into());
        }
        Ok(texto)
    }

    fn status(s: SpeechRecognitionResultStatus) -> String {
        match s {
            SpeechRecognitionResultStatus::TopicLanguageNotSupported => "idioma".into(),
            SpeechRecognitionResultStatus::MicrophoneUnavailable => "microfone".into(),
            SpeechRecognitionResultStatus::NetworkFailure => "rede".into(),
            SpeechRecognitionResultStatus::TimeoutExceeded | SpeechRecognitionResultStatus::UserCanceled => "nada".into(),
            SpeechRecognitionResultStatus::AudioQualityFailure => "audio".into(),
            SpeechRecognitionResultStatus::Unknown => "desconhecido".into(),
            outro => format!("outro: status {}", outro.0),
        }
    }

    pub fn parar() {
        if let Some(rec) = ATUAL.lock().unwrap().take() {
            if let Ok(op) = rec.StopRecognitionAsync() {
                let _ = op.get();
            }
        }
    }
}

#[cfg(windows)]
pub use win::{ouvir, parar};

#[cfg(not(windows))]
pub fn ouvir(_idioma: &str) -> Result<String, String> {
    Err("outro: só no Windows".into())
}

#[cfg(not(windows))]
pub fn parar() {}

/// Abre a tela do Windows onde se liga o "Reconhecimento de fala online".
pub fn abrir_privacidade() {
    let _ = std::process::Command::new("explorer").arg("ms-settings:privacy-speech").spawn();
}
