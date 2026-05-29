ARCHIVE ?=
DEST ?=
OUT ?= ./build

.PHONY: unpack pack pack-sponsor
unpack:
	@test -n "$(ARCHIVE)" || (echo "Użycie: make unpack ARCHIVE=architekt-wolnosci-*.tar.gz [DEST=./]" >&2; exit 1)
	@./scripts/unpack-founders-archive.sh "$(ARCHIVE)" "$(DEST)"

pack:
	@./scripts/pack-founders-archive.sh "$(OUT)"

pack-sponsor:
	@PACK_SPONSOR=1 ./scripts/pack-founders-archive.sh "$(OUT)"
