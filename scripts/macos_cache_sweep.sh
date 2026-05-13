#!/bin/zsh
# =============================================================================
# macOS (Sequoia itd.) — czyszczenie cache aplikacji + purge pamięci podręcznej
# jądra. NIE „przyspiesza CPU” ani nie wymusza RAM w sposób magiczny — macOS
# sam zarządza pamięcią; purge zwalnia głównie nieaktywne strony cache dysku.
#
# Użycie (jedna komenda z katalogu repo):
#   zsh scripts/macos_cache_sweep.sh
# Opcjonalnie usuń duże paczki VM Claude (oszczędność miejsca — odbudują się):
#   CLAUDE_PURGE_VM_BUNDLES=1 zsh scripts/macos_cache_sweep.sh
#
# Zalecenie: zamknij przeglądarki, Cursor, Claude Desktop i Terminal przed startem.
# =============================================================================
setopt null_glob extended_glob
set +e

die() { print -u2 -- "$*"; exit 1 }
[[ "$(uname)" == Darwin ]] || die "Ten skrypt jest przeznaczony dla macOS."

print -- "→ Czyszczenie cache w \$HOME/Library (bez kasowania profili / logowania)…"

rmrf() {
  local p="$1"
  [[ -e "$p" ]] || return 0
  rm -rf "$p" && print -- "  ✓ $p"
}

# --- Przeglądarki (typowe ścieżki cache; profile zostają) --------------------
rmrf "$HOME/Library/Caches/Google/Chrome"
rmrf "$HOME/Library/Caches/com.google.Chrome"
rmrf "$HOME/Library/Caches/Google/Chrome Canary"
rmrf "$HOME/Library/Caches/Microsoft Edge"
rmrf "$HOME/Library/Caches/com.microsoft.edgemac"
rmrf "$HOME/Library/Caches/Firefox"
rmrf "$HOME/Library/Caches/Mozilla"
rmrf "$HOME/Library/Caches/BraveSoftware"
rmrf "$HOME/Library/Caches/com.brave.Browser"
rmrf "$HOME/Library/Caches/com.operasoftware.Opera"
rmrf "$HOME/Library/Caches/com.vivaldi.Vivaldi"
rmrf "$HOME/Library/Caches/Arc"
rmrf "$HOME/Library/Caches/com.apple.Safari"
rmrf "$HOME/Library/Caches/WebKit"
rmrf "$HOME/Library/Caches/com.apple.WebKit.Networking"
rmrf "$HOME/Library/Caches/com.apple.WebKit.GPU"
# Safari — dodatkowe podkatalogi WebKit (jeśli istnieją)
for p in "$HOME"/Library/Caches/com.apple.WebKit.*(N); do rmrf "$p"; done

# --- Cursor (VS Code–like) ----------------------------------------------------
rmrf "$HOME/Library/Application Support/Cursor/Cache"
rmrf "$HOME/Library/Application Support/Cursor/CachedData"
rmrf "$HOME/Library/Application Support/Cursor/Code Cache"
rmrf "$HOME/Library/Application Support/Cursor/GPUCache"
rmrf "$HOME/Library/Application Support/Cursor/DawnWebGPUCache"
rmrf "$HOME/Library/Application Support/Cursor/CachedExtensions"
rmrf "$HOME/Library/Application Support/Cursor/CachedExtensionVSIXs"
rmrf "$HOME/Library/Caches/Cursor" 2>/dev/null
rmrf "$HOME/Library/Caches/com.todesktop.230313mzl4w4u92" 2>/dev/null

# --- Claude Desktop ----------------------------------------------------------
rmrf "$HOME/Library/Caches/Claude"
rmrf "$HOME/Library/Application Support/Claude/Cache"
rmrf "$HOME/Library/Application Support/Claude/Code Cache"
rmrf "$HOME/Library/Application Support/Claude/GPUCache"
rmrf "$HOME/Library/Application Support/Claude/DawnWebGPUCache"
rmrf "$HOME/Library/Logs/Claude"
if [[ "${CLAUDE_PURGE_VM_BUNDLES:-}" == 1 ]]; then
  rmrf "$HOME/Library/Application Support/Claude/vm_bundles"
  rmrf "$HOME/Library/Application Support/Claude/claude-code-vm"
fi

# --- Grok / xAI (jeśli zainstalowana natywna apka — często tylko web) ---------
rmrf "$HOME/Library/Caches/com.xai.grok" 2>/dev/null
rmrf "$HOME/Library/Application Support/Grok/Cache" 2>/dev/null

# --- Terminal / iTerm2 --------------------------------------------------------
rmrf "$HOME/Library/Caches/com.apple.Terminal"
rmrf "$HOME/Library/Caches/com.googlecode.iterm2"

# --- DNS + wygasłe certyfikaty (szybkie, bez szkody) --------------------------
dscacheutil -flushcache 2>/dev/null || true

print -- ""
print -- "→ purge (kernel) — zwolnienie nieaktywnej pamięci podręcznej dysku."
print -- "  Wymaga hasła administratora (sudo)."
sudo purge && print -- "  ✓ sudo purge zakończone." || print -u2 -- "  ! purge nieudane (anulowano sudo?)"

print -- ""
print -- "Gotowe. Otwórz aplikacje ponownie. Pierwsze uruchomienie może być"
print -- "wolniejsze (cache się odbudowuje) — to normalne."
