# friday

Friday is a fully local linux AI assistant that you can talk to. It can do pretty much everything a common AI chat app does but also interract with your machine. Friday uses [ollama](https://github.com/ollama/ollama), [whisper](https://github.com/openai/whisper), [kokoro](https://github.com/thewh1teagle/kokoro-onnx) and works as a background IPC server

## Some of the things friday can do

- Search the internet
- Open apps, open links in apps
- Run shell commands
- Get selected clipboard content, paste to clipboard 
- Speak
- Read / Write to files
- Remember some settings long term

## Setup

Works only with python 3.13 as for now. Setup with `uv`:

```sh
uv python install 3.13
uv venv --python 3.13 .venv
uv pip install -r requirements.txt 
```

Then copy default config and system prompt to `~/.config/friday/`:

```sh
mkdir -p ~/.config/friday/
cp assets/config.ini ~/.config/friday/
cp assets/system_prompt.md ~/.config/friday/
```

### Voices

```sh
cd ~/.config/friday/
mkdir voices

curl -L -o voices/kokoro-v1.0.onnx \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx

curl -L -o voices/voices-v1.0.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin
```

## Usage

Firstly you have to startup friday daemon, you can start daemon via:

```sh
./fridayd
```

> [!TIP]
> You can startup it acording to the preferred way of your winow manager / DE or via ***systemd service***

You can chat with friday from cli:

```sh
./friday
```

You also dictate a prompt to friday (push to talk), run `./friday --converse` once more to finish dictation

```sh
./friday --converse
```

> [!TIP]
> Setup a key binding in your window manager / desktop environment to run `friday --converse`

You can pass a single question using `-a` argument

```sh
./friday -a 'why is the sky blue?'
```

Friday has a single chat, it does not wipe the chat history untill context window gets to small. It still stores all the messages in a database, so friday can rememeber things from past if you ask it to. If you want to cleanup active chat, use `-w` or `--wipe` or ask friday to wipe current chat history.

```sh
./friday -w
```

> [!NOTE]
> You can configure the way friday manages it's context in `~/.config/friday/config.ini`

### Other commands:
```
usage: friday [-h] [-a ASK] [-I IMAGE [IMAGE ...]] [-A AUDIO [AUDIO ...]] [-c] [-w] [-r] [-s SAY] {serve} ...

Friday is a fully local linux AI assistant. Run without arguments to start an interactive chat.

positional arguments:
  {serve}               available commands
    serve               start friday IPC server

options:
  -h, --help            show this help message and exit
  -a, --ask ASK         ask friday given content (pass as single argument)
  -I, --image IMAGE [IMAGE ...]
                        attach these image[s]. use with --ask
  -A, --audio AUDIO [AUDIO ...]
                        attach audio. use with --ask
  -c, --converse        start recording audio, when run once more - stop recording and get response from friday
  -w, --wipe            wipe current friday context
  -r, --reload          reload running friday server (reloads config, restarts everything)
  -s, --say SAY         make friday say given text
```

## Configuration

Friday is configured via `.ini` config file, take a look at [`~/.config/friday/config.ini`](./assets/config.ini), it is well documented

## Misc 

In order to use onnx GPU runtime on nvidia, additionally install `onnxruntime-gpu` and `cudnn`:

```sh
uv pip install onnxruntime-gpu
```

On archlinux you can install `cudnn` with
```sh
sudo pacman -S cudnn
```

## TODOS

- [ ] GUI in GTK 