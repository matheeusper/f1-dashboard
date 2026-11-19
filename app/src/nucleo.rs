// O nucleo (telemetria + engenheiro, em Python): inicia, espera ficar pronto, para e conversa
// com ele por HTTP local. No .exe final ele vem embutido; em desenvolvimento roda com o uv.
use std::{
    net::UdpSocket,
    process::{Child, Command},
    time::{Duration, Instant},
};

use crate::config;

pub struct Nucleo {
    filho: Option<Child>,
    #[cfg(windows)]
    job: Option<job::Job>,
    pub fonte: String,
    pub compartilhar: bool,
    pub porta_web: u16,
    pub porta_udp: u16,
    pub erro: Option<String>,
    pub iniciando: bool,
    limite: Option<Instant>,
}

impl Nucleo {
    pub fn novo() -> Self {
        let cfg = config::Config::carregar();
        Nucleo {
            filho: None,
            #[cfg(windows)]
            job: None,
            fonte: cfg.fonte,
            compartilhar: cfg.compartilhar,
            porta_web: cfg.porta_web,
            porta_udp: cfg.porta_udp,
            erro: None,
            iniciando: false,
            limite: None,
        }
    }

    pub fn url(&self) -> String {
        format!("http://127.0.0.1:{}", self.porta_web)
    }

    pub fn rodando(&mut self) -> bool {
        match self.filho.as_mut() {
            Some(f) => matches!(f.try_wait(), Ok(None)),
            None => false,
        }
    }

    pub fn parar(&mut self) {
        #[cfg(windows)]
        if let Some(j) = self.job.take() {
            j.encerrar(); // fecha o nucleo e tudo que ele abriu (o uv abre o python)
        }
        if let Some(mut f) = self.filho.take() {
            let _ = f.kill();
            let _ = f.wait();
        }
    }

    /// Para o nucleo atual (se houver) e lanca com a fonte (jogo, demo, tt) e o compartilhamento pedidos.
    /// Depois, `checar` diz quando ficou pronto (assim quem chama nao segura a trava enquanto espera).
    pub fn lancar(&mut self, fonte: &str, compartilhar: bool) -> Result<(), String> {
        self.parar();
        self.fonte = fonte.to_string();
        self.compartilhar = compartilhar;
        self.erro = None;
        self.iniciando = true;
        let r = self.subir();
        if let Err(e) = &r {
            self.falhou(e.clone());
        }
        r
    }

    /// None: ainda subindo. Some(Ok): pronto. Some(Err): falhou (e ja parou o que sobrou).
    pub fn checar(&mut self) -> Option<Result<(), String>> {
        if !self.iniciando {
            return Some(match &self.erro {
                Some(e) => Err(e.clone()),
                None => Ok(()),
            });
        }
        if !self.rodando() {
            let e = format!(
                "o núcleo fechou ao iniciar: as portas {} (UDP) ou {} podem estar em uso por outro programa",
                self.porta_udp, self.porta_web
            );
            self.falhou(e.clone());
            return Some(Err(e));
        }
        if get(self.porta_web, "/state").is_ok() {
            self.iniciando = false;
            return Some(Ok(()));
        }
        if self.limite.map_or(false, |l| Instant::now() > l) {
            let e = "o núcleo não respondeu a tempo".to_string();
            self.falhou(e.clone());
            return Some(Err(e));
        }
        None
    }

    fn falhou(&mut self, e: String) {
        self.erro = Some(e);
        self.iniciando = false;
        self.parar();
    }

    fn subir(&mut self) -> Result<(), String> {
        let mut cmd = comando_base()?;
        cmd.args(["--porta-udp", &self.porta_udp.to_string(), "--porta-web", &self.porta_web.to_string()]);
        match self.fonte.as_str() {
            "demo" => {
                cmd.arg("--demo");
            }
            "tt" => {
                cmd.args(["--demo", "--time-trial"]);
            }
            _ => {}
        }
        if self.compartilhar {
            cmd.arg("--lan");
        }
        cmd.env("PAINELF1_DADOS", config::pasta_dados());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: sem janela preta
        }
        let filho = cmd.spawn().map_err(|e| format!("não consegui iniciar o núcleo: {e}"))?;
        #[cfg(windows)]
        {
            self.job = job::Job::novo(&filho).ok();
        }
        self.filho = Some(filho);
        self.limite = Some(Instant::now() + Duration::from_secs(60)); // a 1a vez com o uv pode demorar
        Ok(())
    }
}

impl Drop for Nucleo {
    fn drop(&mut self) {
        self.parar();
    }
}

/// Como rodar o nucleo: embutido no .exe (versao final) ou pelo codigo com o uv (desenvolvimento).
fn comando_base() -> Result<Command, String> {
    #[cfg(nucleo_embutido)]
    {
        return Ok(Command::new(embutido::extrair()?));
    }
    #[allow(unreachable_code)]
    {
        let repo = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf();
        let mut c = Command::new("uv");
        c.args(["run", "-q", "--project"]).arg(&repo).arg("python").arg(repo.join("server.py"));
        c.current_dir(&repo);
        Ok(c)
    }
}

#[cfg(nucleo_embutido)]
mod embutido {
    use std::{fs, path::PathBuf};

    static NUCLEO: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/nucleo.exe"));

    /// Copia o nucleo para %LOCALAPPDATA%\PainelF1 (uma vez por versao) e devolve o caminho.
    pub fn extrair() -> Result<PathBuf, String> {
        let mut h: u64 = 0xcbf29ce484222325; // FNV-1a: o nome muda quando o nucleo muda
        for b in NUCLEO {
            h ^= *b as u64;
            h = h.wrapping_mul(0x100000001b3);
        }
        let base = std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_else(std::env::temp_dir);
        let pasta = base.join("PainelF1");
        fs::create_dir_all(&pasta).map_err(|e| e.to_string())?;
        let exe = pasta.join(format!("nucleo-{h:016x}.exe"));
        if fs::metadata(&exe).map(|m| m.len() as usize).ok() != Some(NUCLEO.len()) {
            fs::write(&exe, NUCLEO).map_err(|e| format!("não consegui preparar o núcleo: {e}"))?;
        }
        Ok(exe)
    }
}

pub fn get(porta: u16, caminho: &str) -> Result<serde_json::Value, String> {
    ureq::get(&format!("http://127.0.0.1:{porta}{caminho}"))
        .timeout(Duration::from_secs(2))
        .call()
        .map_err(|e| e.to_string())?
        .into_json()
        .map_err(|e| e.to_string())
}

pub fn post(porta: u16, caminho: &str, corpo: serde_json::Value) -> Result<(), String> {
    ureq::post(&format!("http://127.0.0.1:{porta}{caminho}"))
        .timeout(Duration::from_secs(3))
        .set("Content-Type", "application/json")
        .send_json(corpo)
        .map(|_| ())
        .map_err(|e| e.to_string())
}

/// IP deste PC na rede local (o que o celular digita). Nao envia nada: so escolhe a interface.
pub fn ip_local() -> Option<String> {
    let s = UdpSocket::bind("0.0.0.0:0").ok()?;
    s.connect("10.255.255.255:1").ok()?;
    Some(s.local_addr().ok()?.ip().to_string())
}

#[cfg(windows)]
mod job {
    // Job do Windows: se o app fechar (ou travar), o nucleo e o que ele abriu fecham junto.
    use std::{os::windows::io::AsRawHandle, process::Child};
    use windows::Win32::{
        Foundation::{CloseHandle, HANDLE},
        System::JobObjects::{
            AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation, SetInformationJobObject,
            TerminateJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        },
    };

    pub struct Job(HANDLE);
    unsafe impl Send for Job {}

    impl Job {
        pub fn novo(filho: &Child) -> windows::core::Result<Job> {
            unsafe {
                let h = CreateJobObjectW(None, windows::core::PCWSTR::null())?;
                let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                SetInformationJobObject(
                    h,
                    JobObjectExtendedLimitInformation,
                    &info as *const _ as *const _,
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                )?;
                AssignProcessToJobObject(h, HANDLE(filho.as_raw_handle()))?;
                Ok(Job(h))
            }
        }

        pub fn encerrar(self) {
            unsafe {
                let _ = TerminateJobObject(self.0, 1);
            }
        }
    }

    impl Drop for Job {
        fn drop(&mut self) {
            unsafe {
                let _ = CloseHandle(self.0);
            }
        }
    }
}
