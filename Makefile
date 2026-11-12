APP := /usr/local/lib/friday
UV  := $(shell command -v uv)

EXTRAS ?=
EXTRA_ARGS := $(foreach extra,$(EXTRAS),--extra $(extra))

.PHONY: install uninstall

install:
	mkdir -p $(APP)
	tar --exclude=.git --exclude=.venv -cf - . | tar -C $(APP) -xf -
	"$(UV)" sync --project $(APP) --locked $(EXTRA_ARGS)
	ln -sf $(APP)/fridayd /usr/local/bin/fridayd
	ln -sf $(APP)/friday /usr/local/bin/friday

uninstall:
	rm -f /usr/local/bin/friday /usr/local/bin/fridayd
	rm -rf $(APP)
