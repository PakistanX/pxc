# Sample Activities

This directory contains reference PXC activities that demonstrate the standard. Each subdirectory is a self-contained activity with a `manifest.json` and a client-side script. Most also include a server-side sandbox script (`sandbox.js`) that is compiled to a WebAssembly component (`sandbox.wasm`).

For the full specification of the activity format, see the [Activity API Reference](../src/pxc/lib/README.md#activity-api-reference).

## Activities

| Activity | Description | Sandbox |
|----------|-------------|:-------:|
| [chat](./chat/) | Real-time collaborative chat with log-backed message history | Yes |
| [chess](./chess/) | Turn-based chess game with player management and game records | Yes |
| [collab-editor](./collab-editor/) | Collaborative text editor with Yjs synchronization and markdown rendering | Yes |
| [email-prompt-craft](./email-prompt-craft/) | Prompt-engineering exercise: write/iterate a prompt, generate a professional email via Claude Haiku, auto-graded against a rubric (uses HTTP and grading capabilities) | Yes |
| [flappy-bird](./flappy-bird/) | Flappy bird game with personal best scores and course-wide leaderboard | Yes |
| [flashcards](./flashcards/) | Spaced-repetition flip cards with author-selectable SM-2 or binary rating | Yes |
| [helloworld](./helloworld/) | Minimal "Hello World" activity demonstrating basic PXC setup | No |
| [image](./image/) | Image upload and storage activity using file storage capability | Yes |
| [interactive-video](./interactive-video/) | YouTube video with embedded MCQ interactions at configured timestamps | Yes |
| [markdown](./markdown/) | Markdown content block with live editing and HTML rendering | Yes |
| [math](./math/) | Math problem with answer validation and per-user score tracking | Yes |
| [mcq](./mcq/) | Multiple choice question with configurable answers and grading | Yes |
| [python](./python/) | Python coding exercise with Pyodide-based in-browser execution | Yes |
| [quiz](./quiz/) | Minimal client-only quiz (no server sandbox) | No |
| [scorm](./scorm/) | SCORM content player with file storage and entry point configuration | Yes |
| [slideshow](./slideshow/) | HTML slide presentation using Reveal.js | Yes |
| [video](./video/) | HTML5 video player with configurable URL | Yes |
| [youtube](./youtube/) | YouTube video player with configurable video ID | Yes |
| [zoom](./zoom/) | Zoom meeting integration with OAuth and meeting creation (uses HTTP capability) | Yes |

## Building

Build all server-side WASM modules:

```bash
make samples
```

To build a single activity:

```bash
make -C samples/my-activity build
```

## Creating a New Activity

An activity needs at minimum a `manifest.json` and a `ui.js`. See the [mcq](./mcq/) activity for a straightforward example with server-side grading, or [quiz](./quiz/) for a minimal client-only activity.
