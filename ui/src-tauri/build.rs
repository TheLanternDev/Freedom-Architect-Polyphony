fn main() {
    // Pozwala na użycie #[cfg(mobile)] / #[cfg(desktop)] bez warningów
    println!("cargo::rustc-check-cfg=cfg(mobile)");
    println!("cargo::rustc-check-cfg=cfg(desktop)");

    tauri_build::build()
}
