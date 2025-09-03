# Kodi Add-on Compliance Guide (For Official Repository Submission)

> This document summarizes common **requirements and best practices** for designing a Kodi add-on that is **eligible for inclusion** in the official Kodi repository. It is not a substitute for the official rules; always verify against the current Kodi submission guidelines and PR review feedback.

---

## 1) Licensing & Source Integrity
- **Open-source license** compatible with the Kodi repo (e.g., GPL-2.0-or-later, MIT, Apache-2.0). Include a `LICENSE` file.
- **No obfuscation or minification**. All source code and build scripts must be clear and reviewable.
- **No bundled closed-source binaries** unless approved (binary add-ons have separate processes).
- Third-party libraries should be **declared as dependencies** (e.g., `script.module.*`) rather than vendored when possible.

---

## 2) Repository & Packaging Structure
- Standard layout:  
  - `addon.xml` (metadata, dependencies, python requirement, extension points)  
  - `icon.png` (512x512), `fanart.jpg` (1920x1080)  
  - `resources/language/resource.language.xx_xx/strings.po` (localization)  
  - `resources/lib/...` (Python modules)  
  - `changelog.txt` (versioned changes)  
  - `LICENSE` (project license)  
- The **directory name** must match the `id` in `addon.xml`.
- Ensure **consistent versioning** in `addon.xml` and `changelog.txt` (semantic versions preferred).

---

## 3) Python & Compatibility
- **Python 3 only** (Kodi 19+). Declare in `addon.xml` (e.g., `<import addon="xbmc.python" version="3.0.0" />`).
- Avoid using APIs only available in newer Kodi versions unless **guarded**; document minimum supported version (e.g., Matrix 19).
- Handle **JSON-RPC differences** (properties/uniqueid handling) between v19 and v20+ gracefully.
- No long-running/blocking work on the UI thread; use services or background tasks where appropriate.

---

## 4) Network, Privacy & External Services
- Add-on must function **without mandatory external accounts** where feasible, or clearly **degrade gracefully** when not configured.
- **User opt-in** for external services (e.g., remote search). No automatic background calls without consent.
- **No tracking/telemetry** beyond what is necessary. If diagnostics are optional, require a user setting with clear notice.
- **Timeouts and error handling** are required for all network operations.
- Do not ship **private API keys**. If keys are user-provided, store securely via Kodi settings. Mask sensitive values in logs.

---

## 5) Content & Legal
- Respect **copyright** and **terms of service** of all services.
- Do **not** facilitate access to infringing or restricted content. Avoid promoting piracy.
- Use **official brand assets** only as permitted; follow Kodi **trademark** usage.
- Ensure **age-restricted** features (if any) follow platform rules (typically out-of-scope for the official repo).

---

## 6) Metadata & UX Quality
- `addon.xml` must include: id, name, version, provider-name, summary, description, platform, license, and minimum xbmc.python import.
- Provide **localization** for user-visible strings via `strings.po` files (at least English).
- **Cache localized strings**: Use `@lru_cache` decorator for string lookups to improve performance in menus with many items.
- **Color coding**: Use Kodi-style color codes for different action types (destructive, additive, modify).
- **Context-aware menus**: Implement tools and options that adapt based on the current context.
- **Universal context menus**: Support context menu integration for all media types including plugin content.
- **Plugin compatibility**: Handle various plugin item formats and metadata extraction gracefully.
- Include **icon** and **fanart** that meet the size/format requirements and are your own or properly licensed.
- Provide **clean UI/UX**: avoid modal spam, respect back/exit behaviors, and keep logs readable.
- Follow **GUI guidelines**: set `IsPlayable` appropriately, use sort methods, and do not force skin-specific behaviors unless optional.
- **Version compatibility**: Handle Kodi version differences gracefully (e.g., InfoTagVideo API changes between v19 and v20+).

---

## 7) Dependencies
- Declare **all dependencies** in `addon.xml` under `<requires>`.
- Prefer **script.module.* packages** provided by the Kodi repo. If a dependency is missing, consider **submitting it separately**.
- **No bundled dependencies**: Avoid vendoring large libraries - use script.module packages instead.

---

## 8) File Structure & Organization
- **Entry points**: `plugin.py` for main plugin functionality, `service.py` for background service.
- **Modular architecture**: Organize code into logical modules (ui/, data/, kodi/, search/, etc.).
- **Separation of concerns**: Keep UI logic, data access, and business logic in separate modules.
- **Resource management**: Store language files, settings XML, and assets in `resources/` folder.

Example structure:
```
lib/
├── ui/           # UI layer - routing, handlers, builders
├── data/         # Data layer - database, queries, migrations  
├── kodi/         # Kodi-specific integration
├── search/       # Search functionality
├── import_export/ # Import/export engines
├── library/      # Library scanning and indexing
├── auth/         # Authentication and token management
├── config/       # Configuration management
└── utils/        # Shared utilities
```

---

## 9) Performance & Resource Use
- Use **incremental/batched** operations (e.g., JSON-RPC batching) and **deferred loading** for heavy metadata.
- Keep memory footprint low; avoid caching megabyte-scale blobs in RAM when unnecessary.
- Optimize SQLite via **parameterized queries, indexes, transactions, WAL**, and minimal schema migrations.
- Avoid hot loops in the UI thread; throttle background services.
- **Connection pooling**: Use singleton patterns for database connections and API clients.
- **Chunked requests**: Limit JSON-RPC requests to reasonable page sizes (≤200 items).
- **Delta scanning**: Implement incremental library updates to avoid full rescans.
- **Background services**: Respect playback state - never perform heavy operations during video playback.

---

## 9) Logging & Error Handling
- Use Kodi logging APIs consistently; **no excessive logging** at INFO level.
- Do not log secrets or personal data. Redact tokens/URLs with embedded credentials.
- Fail gracefully: **clear error dialogs** or notifications on user actions; continue when safe.

---

## 10) Specific Tips for LibraryGenie
- **Local-first**: Lists/folders and import/export work entirely offline. External search/similarity disabled until user authorizes (OTP workflow).
- **Universal context menus**: Context menu script (`context.py`) handles all playable media types including plugin content from any addon.
- **Plugin item support**: Gather appropriate metadata from focused plugin items for external type storage.
- **Privacy**: Only IMDb IDs, minimal non private data (and user-entered search text) are sent during optional external operations.
- **Compatibility**: Handle `uniqueid.imdb` vs `imdbnumber` differences in Kodi 19/20; guard property sets accordingly.
- **NDJSON export**: Keep schema versioned; include a `schema_version` field and migration notes in the README.
- **Accessibility**: Ensure labels are localized; avoid hard-coded strings.
- **Graceful degradation**: If network features are unavailable, hide/disable related menu items without breaking core features.
- **Differential sync**: Use client-side diff computation and version checking to minimize server requests.
- **Service constraints**: Background sync must respect playback state and include generous rate limiting.
- **State management**: Persist local snapshots, server metadata, and pending operations across addon restarts.

---

## 12) Checklist Before PR
- [ ] `addon.xml` complete, valid, and minimal Python version declared.  
- [ ] License file included; third-party licenses accounted for.  
- [ ] Icons/fanart meet size and licensing requirements.  
- [ ] No obfuscation or private keys in the repo.  
- [ ] Strings localized; English provided.  
- [ ] Dependencies declared; large libs not vendored without reason.  
- [ ] Extensive logs removed or gated by a debug setting.  
- [ ] Network calls are opt-in, timeout-equipped, and error-safe.  
- [ ] Schema/versioning notes updated; migrations tested.  
- [ ] Tested on Kodi 19+ with small and large libraries.
- [ ] Background service respects playback state and includes rate limiting.
- [ ] Sync operations use idempotency keys and handle partial failures gracefully.
- [ ] State persistence works correctly across addon restarts and crashes.
- [ ] Modular architecture with proper separation of concerns.
- [ ] Router-based action handling for maintainable URL routing.
- [ ] Favorites integration tested with various XML formats and edge cases.
- [ ] Info hijack functionality (if enabled) tested across Kodi versions.
- [ ] ListItem builder handles both library and external items correctly.
- [ ] Authentication flow tested with proper token refresh handling.

---