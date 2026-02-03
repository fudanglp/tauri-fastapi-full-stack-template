use once_cell::sync::Lazy;
use serde::Deserialize;
use std::path::PathBuf;
use std::time::Duration;

fn default_host() -> String {
    "127.0.0.1".into()
}

fn default_port() -> u16 {
    1430
}

fn default_data_dir() -> PathBuf {
    ".".into()
}

fn default_health_check_timeout_secs() -> u64 {
    30
}

fn default_health_check_interval_ms() -> u64 {
    200
}

#[derive(Deserialize, Debug)]
pub struct Settings {
    #[serde(default = "default_host")]
    pub host: String,

    #[serde(default = "default_port")]
    pub port: u16,

    #[serde(default = "default_data_dir")]
    pub data_dir: PathBuf,

    #[serde(default = "default_health_check_timeout_secs")]
    pub health_check_timeout_secs: u64,

    #[serde(default = "default_health_check_interval_ms")]
    pub health_check_interval_ms: u64,
}

impl Settings {
    pub fn from_env() -> Self {
        envy::from_env().expect("Failed to load settings from environment")
    }

    pub fn is_dev_mode() -> bool {
        cfg!(debug_assertions)
    }

    pub fn backend_url(&self) -> String {
        format!("http://{}:{}", self.host, self.port)
    }

    pub fn health_endpoint(&self) -> String {
        format!("{}/api/v1/health", self.backend_url())
    }

    pub fn health_check_timeout(&self) -> Duration {
        Duration::from_secs(self.health_check_timeout_secs)
    }

    pub fn health_check_interval(&self) -> Duration {
        Duration::from_millis(self.health_check_interval_ms)
    }
}

/// Global settings singleton (similar to pydantic's `settings = Settings()`)
pub static SETTINGS: Lazy<Settings> = Lazy::new(Settings::from_env);
