APP := /usr/local/lib/friday
UV  := $(shell command -v uv)

EXTRAS ?=
EXTRA_ARGS := $(foreach extra,$(EXTRAS),--extra $(extra))
USER_SYSTEMD_DIR := $(HOME)/.config/systemd/user

.PHONY: install uninstall install-app install-misc install-service uninstall-service

install: install-app install-misc
	$(MAKE) install-service

install-app:
	sudo mkdir -p $(APP)
	sudo mkdir -p /etc/friday/
	tar --exclude=.git --exclude=.venv -cf - . | sudo tar -C $(APP) -xf -
	sudo "$(UV)" sync --project $(APP) --locked $(EXTRA_ARGS)
	sudo ln -sf $(APP)/fridayd /usr/local/bin/fridayd
	sudo ln -sf $(APP)/friday /usr/local/bin/friday
	sudo cp assets/config.ini /etc/friday/

install-service:
	install -D -m 0644 assets/friday.service $(USER_SYSTEMD_DIR)/friday.service
	systemctl --user daemon-reload
	systemctl --user enable --now friday.service	

install-misc:
	mkdir -p ~/.config/friday/voices/

	test -e ~/.config/friday/config.ini || cp assets/config.ini ~/.config/friday/
	test -e ~/.config/friday/system_prompt.md || cp assets/system_prompt.md ~/.config/friday/

	test -e ~/.config/friday/voices/kokoro-v1.0.onnx || curl -L -o ~/.config/friday/voices/kokoro-v1.0.onnx \
		https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx

	test -e ~/.config/friday/voices/voices-v1.0.bin || curl -L -o ~/.config/friday/voices/voices-v1.0.bin \
		https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin

uninstall: uninstall-service
	sudo rm -f /usr/local/bin/friday /usr/local/bin/fridayd
	sudo rm -rf $(APP)

uninstall-service:
	-systemctl --user disable --now friday.service
	rm -f $(USER_SYSTEMD_DIR)/friday.service
	systemctl --user daemon-reload
