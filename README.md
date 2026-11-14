<h1 align="center">
  <img width="320" height="100" alt="friday(1)" src="https://github.com/user-attachments/assets/c53d22c8-3ce7-438f-9180-b725459b8ce0" />
</h1>

<p align="center">
  <strong>A local Linux AI assistant that can actually get things done.</strong><br />
  Talk to Friday, and it can search the web, open apps, run shell commands, work with your files, clipboard, all from your machine.
</p>

<p align="center">
  Friday uses Ollama for AI, Whisper for speech recognition, and Kokoro for speech. It runs in the background as an IPC server, ready to help from the command line or your desktop.
</p>

## Friday can:

- Search the web for answers
- Open apps and launch links in your default apps
- Run shell commands
- Read and write files
- Work with your clipboard
- Check Gmail, Google Tasks, and Calendar with optional Google integrations
- Run skills
- Listen to voice prompts and speak its replies
- Remember settings and useful details over time
- Call you boss, Tony

## Usage

> [!IMPORTANT]
> Friday needs a running daemon, you can install it as a sytemd user service (see [installation](#installation)), or startup it manully by running `fridayd`

You can chat with friday from cli:

```sh
friday
```

You can also dictate a prompt to friday (push to talk), run `./friday --converse` once more to finish dictation

```sh
friday --converse
```

> [!TIP]
> Setup a key binding in your window manager / desktop environment to run `friday --converse`

You can pass a question like this:

```sh
friday "hey there, what is my battery level?"
```

Friday has a single chat, it does not wipe the chat history until context window gets to small. It still stores all the messages in a database, so friday can remember things from past if you ask it to. If you want to cleanup active chat, use `-w` or `--wipe` or ask friday to wipe current chat history.

```sh
friday -w
```

> [!NOTE]
> You can configure the way friday manages it's context in `~/.config/friday/config.ini`

## Installation

Requirements:

- uv (for setup)
- [Ollama](https://github.com/ollama/ollama)

Example configuration uses `gemma4:e2b` ollama model. Make sure the model is available before starting Friday:

```sh
ollama pull gemma4:e2b
```

<details open>
  <summary><h3>System wide installation</h3></summary>

In order to setup everything and install `friday` and `fridayd` (will also install and startup a systemd service for friday daemon): 

```sh
make install
```

*If you need multi-language support and GPU runtime for TTS and speech-to-text:* add these as EXTRAS

```sh
make install EXTRAS="lang gpu"
```

Then you have to enable systemd service:

> [!NOTE]
> Standalone window managers may not pass the graphical-session environment to `friday.service`, causing some features to fail (opening apps, opening content in apps). ***If that happens, start `fridayd` through your window manager’s autostart instead.***

```
systemctl --user daemon-reload
systemctl --user enable --now friday.service
```

Uninstall with:

```sh
make uninstall
```

</details>

<details>
  <summary><h3>Project setup / for development</h3></summary>

If you need basic features only:

```sh
uv sync --locked
```

*If you need multi-language support:*

```sh
uv sync --locked --extra lang
```

*If you need GPU runtime for TTS and speech-to-text:*

```sh
uv sync --locked --extra gpu
```

#### Configuration files, voices, system prompts

Run this to install default config file, voices and system prompt

```sh
make install-misc
```

#### Start daemon

You can start daemon via `./fridayd`:

```sh
./fridayd
```

</details>

## Configuration

Friday is configured via `.ini` config file, take a look at [`~/.config/friday/config.ini`](./assets/config.ini), it is well documented. **After modifying config file, relaod friday daemon**, you can do it with `friday --reload`

### Ollama settings (`[ai]`)

| Setting | Default | Purpose |
|---|---|---|
| `model` | `gemma4:e2b` | Ollama model used for chat |
| `think` | `true` | Enables thinking when supported by the model |
| `use_tools` | `true` | Allows the model to use tools (any kind of advanced interaction) |
| `keep_alive` | `30m` | How long Ollama keeps the model loaded after a message |
| `num_ctx` | `16384` | Maximum context window configured for the model |
| `preload` | `true` | Loads the Ollama model at startup |

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
| `enable_thinking_quotes` | `true` | Say thinking quotes |
| `web_search_provider` | `ddgs` | Web search backend: `none`, `ddgs`, `ollama`, or `searxng` |
| `searxng_url` | `http://localhost:8888/` | SearXNG endpoint when using that provider |
| `screenshot_cmd` | `~/.local/bin/screenshot` | Command Friday uses to take a screenshot when requested |
| `keep_recent_turns` | `3` | Number of recent conversation turns kept in active context |
| `context_reserve` | `2000` | Tokens reserved for the response and tool use |
| `max_tool_response_length` | `20000` | Maximum tool response length in characters |
| `max_response_trim_content` | `true` | Trims oversized tool responses to the configured limit |
| `send_notifications` | `true` | Sends desktop notifications (requires `notify-send`) |
| `log_thinking` | `false` | Logs the model's thinking process when running the daemon |
| `use_google_tools` | `false` | Enable google integrations. [See section below](#google-integrations--gmail-tasks-and-calendar) |
| `wipe_chat_on_daemon_startup` | `false` | Clears the active chat when the daemon starts |
| `preserve_tool_responses` | `false` | Saves tool responses in chat history; setting it to `false` reduces context usage |
| `thinking_quotes` | A list of phrases | Phrases Friday can say while thinking; used when `enable_thinking_quotes` is `true` |

The `ddgs` provider searches the web using the Python library. The `ollama` provider uses Ollama's web-search functions and requires an `OLLAMA_API_KEY`. The `searxng` provider requires a SearXNG server with its JSON API enabled and additional python dependencies: `requests` and `trafilatura`.

## Skills 

Friday supports [Agent skills](https://agentskills.io/home), you can install skills to `~/.config/friday/skills/`. 

Example skill (save as `~/.config/friday/skills/good-morning/SKILL.md`):

```md
---
name: good-morning
description: Actions user want's you to perform when he says good morning to you. Run this skill whenever user says good morning for the first time
---

# Morning routine

Follow these exact steps:

1. Get weather info with `run_shell("inxi -w --weather-unit m")`, sumarize it, include current day of the week 
2. Check user's email, tasks and sumarize them in a brief maner. 
3. Ask if calendar events wanted
```

## System prompt 

You can also modify default system prompt in order to tweak friday behaviour. Take a look at [`~/.config/friday/system_prompt.md`](./assets/system_prompt.md)

> [!TIP]
> You can also add per-model system prompts, just save it to a markdown file with the model name - `~/.config/friday/gemma4:e4b.md`

## Extra context

Friday also supports an extra context (`~/.config/friday/extra_context.md`) - which is a file with additional prompt. Difference is that ***it does not have system level prompt importance***. Also, model can add content to it. You can add additional facts / commands to it, example content:

```
## Extra context

- To do any music related commands, use `playerctl` shell command. Read manual with `man playerctl`
```

## Google integrations — Gmail, Tasks, and Calendar

You can setup friday to read your latest emails, tasks and even events from calendar, but it requires additional setup: 

### 0. Enable google tools

Set `misc.use_google_tools` to true in [`~/.config/friday/config.ini`](./assets/config.ini)

### 1. Create a Google Cloud project

[Open Google Cloud Console](https://console.cloud.google.com/projectcreate) and create a new project.

### 2. Enable the APIs

Open each API page for your project and click **Enable**:

- [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)
- [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
- [Google Tasks API](https://console.cloud.google.com/apis/library/tasks.googleapis.com)

### 3. Configure the OAuth consent screen

Open Google Auth Platform in your project. Configure the app's name and contact email. Under **Audience**, choose **External** for a personal Gmail account and leave the app in **Testing**. Add the Gmail address you'll sign in with under **Test users**.

### 4. Create and download an OAuth client

In Google Auth Platform, open **Clients**, choose **Create client**, and select **Desktop app**. Create the client, download its JSON file, and save it to `~/.config/friday/` as `credentials.json`.

Now re-run `fridayd`. A browser window will open so you can sign in as the test user and approve access.

**Testing-mode note:** Google limits Testing apps to listed test users, and authorizations for these scopes expire after seven days. You may need to authorize the app again weekly.

## Nvidia GPU support for TTS

Install with `--extra gpu` dependencies, also you will need `cudnn` installed. On Arch Linux, install it with:

```sh
sudo pacman -S cudnn
```

Set `tts.prefer_cpu = false` to allow GPU use where supported. Set it to `true` to prefer CPU execution.

> [!WARNING]
> GPU usage requires enough VRAM. if TTS or speech recognition does not work, try using CPU instead

### Other commands:

```
usage: friday [-h] [--serve] [-l LOG_LEVEL] [-m MODEL] [-I IMAGE [IMAGE ...]] [-A AUDIO [AUDIO ...]] [-s] [-o] [--think | --no-think] [-M SET_MODEL] [-c] [-w] [-r]
              [--no-thinking-quote] [--say TEXT]
              
Friday is a fully local linux AI assistant. Run without arguments to start an interactive chat.

positional arguments:
  [CONTENT]             content to send to Friday

options:
  -h, --help            show this help message and exit
  --serve               start friday IPC server
  -l, --log-level LOG_LEVEL
                        log verbosity from 0 (least output) to 4 (most output). Examples: 4 - includes debug, info, warnings, and errors, 2 - includes warnings and errors.
  -m, --model MODEL     answer given content using this model
  -I, --image IMAGE [IMAGE ...]
                        attach these image[s]
  -A, --audio AUDIO [AUDIO ...]
                        attach audio
  -s, --silent          do not speak responses aloud
  -o, --one-shot        answer given content in an empty context, do not store in history afterwards
  --think, --no-think   enable or disable thinking (overwrites config default)
  -M, --set-model SET_MODEL
                        set model to given one at runtime without server reloading
  -c, --converse        start recording audio, when run once more - stop recording and get response from friday
  -w, --wipe            wipe current friday context
  -r, --reload          reload running friday server (reloads config, restarts everything). Note that some of the settings might still need a full server restart
  --no-thinking-quote   just don't say random thinking quote
  --say TEXT            make friday say given text
```

## TODOS

- [ ] GUI in GTK 
- [x] Create normal packaging + systemd service
- [x] Improve IPC communication, better schema
- [x] More handling for runtime model change + improve reloading
- [x] Per model system prompt support
- [x] Integrations with gmail, google calendar
- [x] Improved chat context management - sort of additional old chats summary prompt

## Thanks

- [Papirus Icon theme](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme) for syncthing icon looks
- [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) for TTS library
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) for fast speech recognition library
