// Ouvir a pergunta pelo microfone e transcrever com o Whisper, rodando no proprio PC (offline).
// Dentro da janela do app (WebView2) o reconhecimento do Chrome nao existe, entao quem ouve e o app;
// a pagina so mostra "Ouvindo…" e manda o texto ao engenheiro.
//
// - grava do microfone padrao e para sozinho ~1 s depois que voce para de falar;
// - na primeira vez baixa o modelo (ggml-base, ~150 MB) para dados/modelos;
// - erros voltam como codigos curtos que a pagina traduz: "microfone", "nada", "modelo", "outro: ...".
use std::{
    fs,
    io::{Read, Write},
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, AtomicU32, Ordering},
        Arc, Mutex, OnceLock,
    },
    time::{Duration, Instant},
};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use serde::Serialize;
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

use crate::config;

const MODELO: &str = "ggml-base.bin";
const URL_MODELO: &str = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin";
const TAXA: u32 = 16_000; // o Whisper trabalha com 16 kHz mono

static PARAR: AtomicBool = AtomicBool::new(false);
static FASE: Mutex<&'static str> = Mutex::new("parado"); // parado, baixando, ouvindo, entendendo
static BAIXADO: AtomicU32 = AtomicU32::new(0); // % do download do modelo
static CONTEXTO: OnceLock<Mutex<Option<WhisperContext>>> = OnceLock::new();

#[derive(Serialize)]
pub struct EstadoOuvido {
    fase: &'static str,
    baixado: u32,
}

pub fn estado() -> EstadoOuvido {
    EstadoOuvido { fase: *FASE.lock().unwrap(), baixado: BAIXADO.load(Ordering::SeqCst) }
}

fn fase(f: &'static str) {
    *FASE.lock().unwrap() = f;
}

pub fn parar() {
    PARAR.store(true, Ordering::SeqCst);
}

pub fn ouvir(idioma: &str) -> Result<String, String> {
    PARAR.store(false, Ordering::SeqCst);
    let r = (|| {
        let modelo = garantir_modelo()?;
        fase("ouvindo");
        let audio = gravar()?;
        fase("entendendo");
        transcrever(&modelo, &audio, idioma)
    })();
    fase("parado");
    r
}

// ------------------------------------------------------------------ modelo
fn caminho_modelo() -> PathBuf {
    config::pasta_dados().join("modelos").join(MODELO)
}

/// Baixa o modelo na primeira vez (para um .part e so depois renomeia: download pela metade nao vale).
fn garantir_modelo() -> Result<PathBuf, String> {
    let destino = caminho_modelo();
    if destino.exists() {
        return Ok(destino);
    }
    fase("baixando");
    BAIXADO.store(0, Ordering::SeqCst);
    let _ = fs::create_dir_all(destino.parent().unwrap());
    let parte = destino.with_extension("part");
    let resp = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(15))
        .build()
        .get(URL_MODELO)
        .call()
        .map_err(|e| format!("modelo: {e}"))?;
    let total: u64 = resp.header("Content-Length").and_then(|v| v.parse().ok()).unwrap_or(147_951_465);
    let mut leitor = resp.into_reader();
    let mut arq = fs::File::create(&parte).map_err(|e| format!("modelo: {e}"))?;
    let mut buf = vec![0u8; 1 << 16];
    let mut feito: u64 = 0;
    loop {
        let n = leitor.read(&mut buf).map_err(|e| format!("modelo: {e}"))?;
        if n == 0 {
            break;
        }
        arq.write_all(&buf[..n]).map_err(|e| format!("modelo: {e}"))?;
        feito += n as u64;
        BAIXADO.store(((feito * 100) / total.max(1)).min(100) as u32, Ordering::SeqCst);
    }
    drop(arq);
    if feito < 10_000_000 {
        let _ = fs::remove_file(&parte);
        return Err("modelo: download incompleto".into());
    }
    fs::rename(&parte, &destino).map_err(|e| format!("modelo: {e}"))?;
    Ok(destino)
}

// ------------------------------------------------------------------ microfone
/// Grava do microfone padrao ate voce parar de falar. Devolve o audio em 16 kHz mono.
fn gravar() -> Result<Vec<f32>, String> {
    let host = cpal::default_host();
    let disp = host.default_input_device().ok_or("microfone")?;
    let cfg = disp.default_input_config().map_err(|_| "microfone".to_string())?;
    let taxa = cfg.sample_rate();
    let canais = cfg.channels() as usize;
    let amostras = Arc::new(Mutex::new(Vec::<f32>::with_capacity(taxa as usize * 10)));

    let erro = |e| eprintln!("microfone: {e}");
    let stream = {
        let a = amostras.clone();
        let mono = move |dados: &mut dyn Iterator<Item = f32>| {
            let mut v = a.lock().unwrap();
            let mut soma = 0.0;
            let mut n = 0;
            for x in dados {
                soma += x;
                n += 1;
                if n == canais {
                    v.push(soma / canais as f32);
                    soma = 0.0;
                    n = 0;
                }
            }
        };
        match cfg.sample_format() {
            cpal::SampleFormat::F32 => disp.build_input_stream(
                cfg.config(),
                move |d: &[f32], _: &_| mono(&mut d.iter().copied()),
                erro,
                None,
            ),
            cpal::SampleFormat::I16 => disp.build_input_stream(
                cfg.config(),
                move |d: &[i16], _: &_| mono(&mut d.iter().map(|x| *x as f32 / 32768.0)),
                erro,
                None,
            ),
            cpal::SampleFormat::U16 => disp.build_input_stream(
                cfg.config(),
                move |d: &[u16], _: &_| mono(&mut d.iter().map(|x| (*x as f32 - 32768.0) / 32768.0)),
                erro,
                None,
            ),
            _ => return Err("microfone".into()),
        }
        .map_err(|_| "microfone".to_string())?
    };
    stream.play().map_err(|_| "microfone".to_string())?;

    // detecta a fala pela energia: o comeco define o nivel do ruido de fundo
    let bloco = (taxa / 20) as usize; // 50 ms
    let inicio = Instant::now();
    let mut lido = 0usize;
    let mut ruido: Option<f32> = None;
    let mut falou_em: Option<Instant> = None;
    let mut ultimo_som = Instant::now();
    loop {
        std::thread::sleep(Duration::from_millis(50));
        if PARAR.load(Ordering::SeqCst) {
            break;
        }
        let v = amostras.lock().unwrap();
        while lido + bloco <= v.len() {
            let rms = (v[lido..lido + bloco].iter().map(|x| x * x).sum::<f32>() / bloco as f32).sqrt();
            lido += bloco;
            let base = *ruido.get_or_insert(rms);
            let limiar = (base * 3.0).max(0.012);
            if rms > limiar {
                falou_em.get_or_insert_with(Instant::now);
                ultimo_som = Instant::now();
            } else if falou_em.is_none() {
                ruido = Some(base * 0.95 + rms * 0.05); // ainda em silencio: acompanha o ruido
            }
        }
        drop(v);
        let agora = Instant::now();
        match falou_em {
            None if agora - inicio > Duration::from_secs(5) => {
                drop(stream);
                return Err("nada".into()); // ninguem falou
            }
            Some(_) if agora - ultimo_som > Duration::from_millis(1000) => break, // parou de falar
            Some(f) if agora - f > Duration::from_secs(10) => break, // no maximo 10 s
            _ => {}
        }
    }
    drop(stream);
    if falou_em.is_none() {
        return Err("nada".into());
    }
    let v = amostras.lock().unwrap().clone();
    Ok(reamostrar(&v, taxa, TAXA))
}

/// Interpolacao linear (para a voz, para o Whisper, e o bastante).
fn reamostrar(x: &[f32], de: u32, para: u32) -> Vec<f32> {
    if de == para || x.is_empty() {
        return x.to_vec();
    }
    let passo = de as f64 / para as f64;
    let n = (x.len() as f64 / passo) as usize;
    (0..n)
        .map(|i| {
            let p = i as f64 * passo;
            let j = p as usize;
            let f = (p - j as f64) as f32;
            let a = x[j];
            let b = *x.get(j + 1).unwrap_or(&a);
            a + (b - a) * f
        })
        .collect()
}

// ------------------------------------------------------------------ transcricao
fn transcrever(modelo: &PathBuf, audio: &[f32], idioma: &str) -> Result<String, String> {
    let ctx = CONTEXTO.get_or_init(|| Mutex::new(None));
    let mut guarda = ctx.lock().unwrap();
    if guarda.is_none() {
        let c = WhisperContext::new_with_params(modelo.to_str().unwrap_or_default(), WhisperContextParameters::default())
            .map_err(|e| format!("modelo: {e}"))?;
        *guarda = Some(c);
    }
    let c = guarda.as_ref().unwrap();
    let mut st = c.create_state().map_err(|e| format!("outro: {e}"))?;
    let mut p = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
    let en = idioma == "en";
    p.set_language(Some(if en { "en" } else { "pt" }));
    // vocabulario do radio ajuda o modelo a acertar os termos
    p.set_initial_prompt(if en {
        "Race engineer radio. Tyres, gap, fuel, battery, pit strategy, box, undercut, weather, setup, turn 3, repeat."
    } else {
        "Rádio do engenheiro de F1. Pneus, gap, combustível, bateria, estratégia de pit, box, undercut, clima, acerto, curva 3, repete."
    });
    p.set_n_threads(std::thread::available_parallelism().map_or(4, |n| n.get().min(8)) as i32);
    p.set_no_context(true);
    p.set_single_segment(true);
    p.set_suppress_blank(true);
    p.set_print_progress(false);
    p.set_print_realtime(false);
    p.set_print_special(false);
    p.set_print_timestamps(false);
    // o Whisper precisa de pelo menos ~1 s de audio
    let mut a = audio.to_vec();
    if a.len() < TAXA as usize {
        a.resize(TAXA as usize + TAXA as usize / 4, 0.0);
    }
    st.full(p, &a).map_err(|e| format!("outro: {e}"))?;
    let texto: String = st.as_iter().filter_map(|s| s.to_str_lossy().ok().map(|t| t.into_owned())).collect();
    let texto = texto.trim().to_string();
    if texto.is_empty() || texto.starts_with('[') {
        return Err("nada".into()); // "[BLANK_AUDIO]" e parecidos
    }
    Ok(texto)
}

#[cfg(test)]
mod testes {
    // Transcreve um .wav (16 bits mono) com o modelo ja baixado em target/debug/dados/modelos:
    //   PAINELF1_WAV=pergunta.wav cargo test ouvido -- --ignored --nocapture
    #[test]
    #[ignore]
    fn transcreve_wav() {
        let wav = std::fs::read(std::env::var("PAINELF1_WAV").unwrap()).unwrap();
        let pcm: Vec<f32> = wav[44..].chunks_exact(2).map(|b| i16::from_le_bytes([b[0], b[1]]) as f32 / 32768.0).collect();
        let modelo = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/debug/dados/modelos/ggml-base.bin");
        let t = std::time::Instant::now();
        let texto = super::transcrever(&modelo, &pcm, "pt").unwrap();
        println!("TEXTO: {texto} ({:.1} s)", t.elapsed().as_secs_f32());
    }
}
