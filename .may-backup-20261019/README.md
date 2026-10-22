# MAY — your personal assistant

MAY is a Windows desktop assistant that addresses you as Boss. Its floating orb blends MAY’s teal 3D particle tunnel with an original red-and-blue web pattern and a clear central M. MAY can use a local Ollama model, open and politely close app windows, handle common laptop commands, search the web, summarize recent news in the chat, and speak replies with local Piper voices.

## Start MAY

1. Install Python 3.11 and Ollama for Windows.
2. Open this folder in VS Code or PowerShell.
3. Install packages with `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Install a local model once with `ollama run qwen2.5:3b-instruct`. MAY will reuse the model and stream replies as it generates them.
5. Start MAY by double-clicking `start_may.bat`, or run `.\.venv\Scripts\python.exe .\may_assistant.py`.

MAY begins listening when it starts. The mic control is inside the chat; click **Pause listening** to pause and **Start listening** to resume. Right-click the MAY orb for the same listening control, Windows startup setting, and Exit. Click the orb to show or hide the chat, or drag it to a screen corner.

## What MAY can do

- Say “open Paint”, “Chrome kholo”, “close Chrome”, or “list apps” to manage apps. Closing asks the app window to exit normally, so it can still show its usual save prompt.
- Say “volume down”, “volume up”, “volume kam karo”, “volume badhao”, “आवाज़ कम करो”, or “आवाज़ बढ़ाओ” to control Windows volume by voice. Say “mute” to toggle mute; there are no volume buttons in the chat.
- Say “pause music”, “next song”, or “previous track” to control media playback.
- Ask “what’s my battery?” for charge status, or say “lock my PC” to lock Windows.
- Say “set a timer for 5 minutes”, “remind me in 10 minutes to take a break”, or “cancel timer”. Timers and clock alarms run while MAY remains open. Say “set an alarm for 7:30 AM” or use 24-hour time such as “set an alarm for 19:30”; MAY will speak when it goes off.
- Say “send WhatsApp to +countrycode number saying your message”. MAY opens a prefilled WhatsApp Web draft in Chrome; check the recipient and text, then press Send yourself.
- Say “open Chrome and search for …”, “search … in Chrome”, or “Chrome kholo aur … search karo” to open the Google results in Chrome and prepare an answer in MAY.
- Say “close chat” to hide the chat, or “close MAY” to exit the assistant.
- Ask for current news in English, Hindi, or Hinglish. MAY uses a date-limited news search, summarizes up to four recent stories in the chat, and adds clickable article references. It prefers results from the last day and checks the last week if no fresh results are available.
- Ask other current questions or say “search for …” to get a web-backed answer in the chat with source links.
- Chat naturally in English or Hindi. Latin-script input, including Hinglish, gets an English response and voice; Devanagari input gets Hindi. Everyday conversation stays local; other requests can be handled by Ollama, with web search when current information is needed.
- Say “my name is …” or “mera naam … hai” to save your actual name. MAY will address you as “Boss”.
- Ask “what time is it?” or “what is today’s date?” for your PC’s local time.

## Voice and privacy

- Spoken English uses the local `en_US-hfc_female-medium` Piper voice. Hindi uses `hi_IN-priyamvada-medium`; MAY applies pronunciation and pacing adjustments to improve Hindi speech clarity. The voice runs locally without an ElevenLabs key or TTS network request. The voice datasets are licensed for non-commercial use: [English voice card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/hfc_female/medium/MODEL_CARD) and [Hindi voice card](https://huggingface.co/rhasspy/piper-voices/blob/main/hi/hi_IN/priyamvada/medium/MODEL_CARD).
- Speech recognition sends recognized audio to Google speech recognition in Indian English and Hindi. Web and news queries go to the free `ddgs` search library; those providers can change or rate-limit requests.
- Chat generation uses the Ollama model installed on this laptop. Reply speed and detail depend on that model and the PC’s hardware.
- MAY addresses you as “Boss”. Your saved account name is stored separately in your Windows AppData profile. Conversation history stays in memory while MAY is running.
- App launching uses Windows-registered apps and Start Menu shortcuts; typed text is not run as a shell command.
