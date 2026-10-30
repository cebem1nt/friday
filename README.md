# friday

Friday is a fully local linux AI assistant that you can talk to. It can do pretty much everything a common AI chat app does but also interract with your machine. Friday uses [ollama](https://github.com/ollama/ollama), [whisper](https://github.com/openai/whisper), [kokoro](https://github.com/thewh1teagle/kokoro-onnx) and works as a background IPC server.

## Some of the things friday can do

- Search the internet
- Open apps, open links in apps
- Run shell commands
- Read selected clipboard content and paste to the clipboard
- Speak
- Read / Write to files
- Remember some settings long term

## Requirements

- Linux
- Python 3.13
- [Ollama](https://github.com/ollama/ollama)

Example configuration uses the Ollama model `gemma4:e4b`. Make sure the model is available in Ollama before starting Friday:

```sh
ollama pull gemma4:e4b
```

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
# Ensure ollama is running 
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

### Ollama settings (`[ai]`)

| Setting | Default | Purpose |
|---|---|---|
| `model` | `gemma4:e4b` | Ollama model used for chat |
| `think` | `true` | Enables thinking when supported by the model |
| `use_tools` | `true` | Allows the model to use tools (any kind of advanced interraction) |
| `keep_alive` | `30m` | How long Ollama keeps the model loaded after a message |
| `num_ctx` | `16384` | Maximum context window configured for the model |

### Text to speech (`[tts]`)

| Setting | Default | Purpose |
|---|---|---|
| `model_path` | `~/.config/friday/voices/kokoro-v1.0.onnx` | Kokoro ONNX model file |
| `voices_path` | `~/.config/friday/voices/voices-v1.0.bin` | Kokoro voice data file |
| `voice` | `af_heart` | Voice identifier |
| `language` | `en-us` | Speech language |
| `speed` | `1.0` | Speech rate |
| `prefer_cpu` | `false` | Prefer CPU instead of GPU |
| `preload` | `true` | Load the speech model at startup |
| `unload_after` | `1m` | Unload the speech model after one idle minute |

### Speech to text (`[stt]`)

Speech recognition uses faster-whisper.

| Setting | Default | Purpose |
|---|---|---|
| `model` | `small.en` | Whisper model used for transcription |
| `prefer_cpu` | `false` | Prefer CPU instead of GPU |
| `preload` | `false` | Load the recognition model at startup |
| `unload_after` | `5m` | Unload the recognition model after five idle minutes |

### Other settings (`[misc]`)

| Setting | Default | Purpose |
|---|---|---|
| `rich_formatting` | `true` | Enables rich terminal formatting for chat |
| `web_search_provider` | `ddgs` | Web search backend: `none`, `ddgs`, `ollama`, or `searxng` |
| `searxng_url` | `http://localhost:8888/` | SearXNG endpoint when using that provider |
| `screenshot_cmd` | `~/.local/bin/screenshot` | Command Friday uses to take a screenshot when requested |
| `keep_recent_turns` | `3` | Number of recent conversation turns kept in active context |
| `context_reserve` | `2000` | Tokens reserved for the response and tool use |
| `max_tool_response_length` | `20000` | Maximum tool response length in characters |
| `max_response_trim_content` | `true` | Trims oversized tool responses to the configured limit |
| `send_notifications` | `true` | Sends desktop notifications (requires `notify-send`) |
| `log_thinking` | `false` | Logs the model’s thinking process when running the daemon |
| `wipe_chat_on_daemon_startup` | `false` | Clears the active chat when the daemon starts |

The `ddgs` provider searches the web using the Python library. The `ollama` provider uses Ollama’s web-search functions and requires an `OLLAMA_API_KEY`. The `searxng` provider requires a SearXNG server with its JSON API enabled and additional python dependencies: `requests` and `trafilatura`.

## GPU support for speech

For NVIDIA GPU execution with ONNX Runtime, install the GPU runtime:

```sh
uv pip install onnxruntime-gpu
```

On Arch Linux, install cudnn with:

```sh
sudo pacman -S cudnn
```

Set `prefer_cpu = false` to allow GPU use where supported. Set it to `true` to prefer CPU execution.

> [!WARNING]
> GPU usage requires enough VRAM. if TTS or speech recognition does not work, try using CPU instead

## TODOS

- [ ] GUI in GTK 