# friday

Fully local light linux AI assistant infrastructure built on top of ollama.

## Installation 

Setup with `uv`:

```sh
uv python install 3.13
uv venv --python 3.13 .venv
uv pip install -r requirements.txt 
```

Then copy default config to `~/.config/friday/`:

```sh
mkdir -p ~/.config/friday/
cp assets/config.ini ~/.config/friday/
```

### Voices

```sh
cd ~/.config/friday/
mkdir voices

curl -L -o kokoro-v1.0.onnx \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx

curl -L -o voices-v1.0.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin
```

## Usage

```sh
# Run the IPC server once
./fridayd
```

```sh
# Chat from cli
./friday --chat

# Or dictate a prompt
./friday --converse # Run ./friday --converse once more to submit the prompt
```

## Configuration

You can modify your `~/.config/friday/config.ini`:

```ini

[ai]
# Ollama model to use
model = gemma4:e4b
think = true

# Allow model to use tools (if supported)
# tools are any interractions AI can do. Examples:
#  open apps, search web, look into clipboard, etc..
use_tools = true

# Keep model in memory for N minutes after a message
keep_alive = 30m

# Top limit of firday's context window (in tokens)
# If model does not reply to your request / halucinate, try increasing this limit 
# Use "unlimited" in order to use model's top limit
num_ctx = 16384

[misc]
rich_formatting = true

# The method / library to use for web searching availble options:
# none    -> model won't be able to search the internet
# ddgs    -> python library, local, best option
# ollama  -> use default ollama web search functions (external, requires OLLAMA_API_KEY)
# searxng -> searxng local server, provide url endpoint, requires json API to be enabled,
#            requires installing the following libs: requests, trafilatura (for web_fetch)
web_search_provider = ddgs

searxng_url = http://localhost:8888/

# Friday can take a screenshot of your screen (yes, only if you ask it to)
# given path to the script should print path to the screenshot on success
# Note that screenshots will not be automatically deleted later. 
screenshot_cmd = ~/.local/bin/screenshot

# Amount of turns to forcefully keep in memory.
# Turn is a full round of user prompt - model response, tool calls
keep_recent_turns = 3

# Tokens kept available in the context window for Friday's replies and tool use.
# Older conversation turns that exceed the remaining context budget are archived
# in the database and removed from the active chat history.
context_reserve = 2000

[tts]
# Text to speech model (AI voice)
model_path = ~/.config/friday/voices/kokoro-v1.0.onnx
voices_path = ~/.config/friday/voices/voices-v1.0.bin

voice = af_heart # The voice to use, see https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
prefer_cpu = false # Prefer computing on CPU instead of GPU
pre_allocate = true

[stt]
# Speech to text (Voice recognition model) uses faster-whisper.
# See https://github.com/openai/whisper#available-models-and-languages
model = small.en
prefer_cpu = false # Prefer computing on CPU instead of GPU
pre_allocate = false
```

## Unsorted notes 

In order to use onnx GPU runtime on nvidia, additionally install `onnxruntime-gpu` and `cudnn`:

```sh
uv pip install onnxruntime-gpu
```

On archlinux you can install `cudnn` with
```sh
sudo pacman -S cudnn
```