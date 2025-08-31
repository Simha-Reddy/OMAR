# OMAR

OMAR is a clinical documentation assistant designed for healthcare providers. It streamlines the process of transcribing, summarizing, and exploring patient visit data using AI-powered tools and customizable templates.

## OMAR IS NOT INTENDED FOR CLINICAL USE AT THIS TIME (AUGUST 2025). THIS IS FOR TESTING.
---

## Caveats
This test program has numerous bugs and the code is filled with detritus from many dead ends.

## Features

- Ambient primary care scribe
  - Real-time recording/transcription and AI-assisted progress note generation
  - Customizable prompt templates (SOAP, Discharge, Primary Care, Social Work, etc.)
  - Patient dot-phrases inside prompts and notes: [[name]], [[age]], [[vitals]], [[meds/active]], [[problems/active]], [[allergies]], [[labs]] and time-window variants
- Patient Instructions
  - Generate clear, patient-centered after-visit instructions and export as PDF
- Explore chart data (RAG)
  - Local VistA data: automatically index and query TIU notes for the selected patient (batch fetch, hybrid search, multi-query fusion, keyword counts)
  - "Hey, OMAR": When the session is recording, saying "Hey, Omar" will allow you to query the chart. Go ahead and just say "Hey Omar, show me his most recent A1c" or "Hey Omar, summarize her recent hospitalization". There will be a little delay before it registers; keep going with your visit until it returns.
  - "Show me": Saying or typing "Show me" at the beginning of your chart query will trigger the program to try to find the requested data directly from the chart, without slowing down to use the LLM.
  - Outside records: paste text or drop/upload PDFs; documents are converted to markdown and chunked for querying
  - Hybrid retrieval (semantic + BM25) with answers citing the most relevant source chunks
- VistA integration (best-effort socket client)
  - Select patient, fetch VPR bundle, normalize to FHIR-like structures
  - Retrieve TIU document text (single or batch), list DocumentReferences, and index for RAG
  - Server endpoints for vitals, labs (with panels, summaries, LOINC filter), medications, allergies, and problems
- Smart Modules
  - Create and chain simple “smart” modules that can use Explore/Scribe inputs and run safely in a sandbox
  - Toggle feature flag SAFE_MODULES_ENABLED. (THIS FEATURE IS UNSTABLE AS OF AUGUST 2025)
- Session and Archive
  - Save/restore in-browser session, save full sessions to archives, view and manage transcripts
- Privacy & caching
  - Patient-scoped JSON responses set strict no-store cache headers and include DFN markers. 

---

## Security and Data Handling

- Data scope and session
  - Patient selection is scoped by DFN; API responses include DFN markers and are treated as patient-scoped.
  - Browser session data (e.g., UI state) is kept in sessionStorage/localStorage; the “End Session” action clears these keys.
- Caching and headers
  - Patient JSON routes set Cache-Control: no-store and disable HTTP caching wherever possible.
  - Static assets are cacheable; PHI-bearing responses are not cached.
- Local files and uploads
  - External documents you paste or drop (PDFs/text) are processed into chunks for querying and stored under a session-specific working area.
  - When you clear an index, switch patients, or end the session, temporary chunk files and per-session indices are deleted.
- Transcripts and notes
  - Sessions are auto-saved in archives and deleted after 10 days automatically by default. User can delete archives directly as well.
  - Deleting an item from Archive removes its files from disk.
  - Live microphone audio is streamed for transcription and not retained after segment processing.
- Logs
  - Server logs avoid PHI where possible; errors are redacted to omit raw content. Enable debug logs only in non-production environments.
- External services
  - LLM and speech calls use configured VA-approved Azure resources. No data is sent to third-party endpoints outside configuration.
- User controls
  - Exiting and switching patients explicit deletes working data.

---

## Getting Started

### 1. Clone the Repository (or download from GitHub website)

```sh
git clone https://github.com/Simha-Reddy/OMAR.git
cd OMAR
```

### 2. Install Dependencies

Make sure you have Python 3.8+ and pip installed.

```sh
pip install -r requirements.txt
```

### 3. Configure Environment Variables (.env)

- Copy `.env.example` to `.env` and fill in values.
- Add a cipher.txt to main directory. Cipher needed for VistA. 
- Do not commit `.env` or any secret files. They are ignored by `.gitignore`.

Azure/OpenAI (required for AI features):

```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<your-endpoint>
AZURE_API_VERSION=2024-02-15-preview
AZURE_DEPLOYMENT_NAME=gpt-4
AZURE_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-large
AZURE_SPEECH_KEY=...
```

VistA socket client (only if using VistA features):

```env
VISTA_HOST=<host>
VISTA_PORT=<port>
VISTA_RPC_CONTEXT=OR CPRS GUI CHART
VISTA_ACCESS_CODE=...
VISTA_VERIFY_CODE=...

# Cipher: prefer file-based config to avoid multiline .env issues
VISTARPC_CIPHER_FILE=path\to\cipher.txt
```


### 4. Run the Application

Run `Setup.bat` to install python dependencies

Run `Start_OMAR.bat` which will start run_local_server and open the program in your browser at http://127.0.0.1:5000.

Log in with CPRS ACCESS/VERIFY codes.

---

## Environment Reference

- Azure: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT or AZURE_ENDPOINT, AZURE_API_VERSION, AZURE_DEPLOYMENT_NAME, AZURE_EMBEDDING_DEPLOYMENT_NAME, AZURE_SPEECH_KEY
- Flask: FLASK_SECRET_KEY, SAFE_MODULES_ENABLED
- VistA: VISTA_HOST, VISTA_PORT, VISTA_RPC_CONTEXT, VISTA_ACCESS_CODE, VISTA_VERIFY_CODE
- VistA cipher: VISTARPC_CIPHER_FILE or VISTARPC_CIPHER

The VistA socket client dynamically loads the cipher from `VISTARPC_CIPHER_FILE` or `VISTARPC_CIPHER` at runtime; nothing is hardcoded in source.

---

## Git Hygiene

- `.gitignore` excludes `.env`, `*.env`, `cipher.txt`, transient data folders, and the VS Code workspace file `v_3_0_SimpleScribe.code-workspace`.

---

## Folder Structure

- `templates/` — HTML templates for the web interface and prompts for making notes
- `static/` — JavaScript, CSS, and client assets
- `modules/` — Custom smart modules for chart data exploration

---

## Contributing

1. Fork the repository and create your branch
2. Make your changes and commit them
3. Push to your fork and submit a pull request

## License
MIT license 
(This project is intended for internal VA use and research.)
## Contact

simha.reddy@va.gov
