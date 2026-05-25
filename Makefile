ARCHIVE ?=
DEST ?=

.PHONY: unpack
unpack:
	@test -n "$(ARCHIVE)" || (echo "Użycie: make unpack ARCHIVE=architekt-wolnosci-*.tar.gz [DEST=./]" >&2; exit 1)
	@./scripts/unpack-founders-archive.sh "$(ARCHIVE)" "$(DEST)"
