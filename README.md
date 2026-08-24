# 🎮 Universal Xbox Cloud Save Extractor

[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue.svg)](https://microsoft.com/windows)
[![Language](https://img.shields.io/badge/language-C%2B%2B20%20%7C%20Python%203.10%2B-green.svg)](https://python.org)
[![API](https://img.shields.io/badge/API-Windows%20Runtime%20(WinRT)-orange.svg)](https://learn.microsoft.com/en-us/uwp/api/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

> **Extract and recover Xbox Game Pass & Xbox Live cloud saves for ANY PC or Console title directly from Microsoft's cloud servers — without requiring an active Game Pass subscription, game license, or full game installation.**

---

## 🌟 Why This Exists

When your Xbox Game Pass subscription expires or a game is removed from the catalog:
* Standard Xbox/PC apps refuse to launch or sync saves (`E_GS_NO_ACCESS`, `0x80070002`).
* Direct REST endpoints (`titlestorage.xboxlive.com`, `gsls.xboxlive.com`) return `403 Forbidden` / `400 Bad Request` because they require hardware-bound machine certificates.
* **This Tool** uses a native **C++/WinRT OS-level bridge** combined with a temporary developer package identity. This instructs Windows' built-in Gaming Services to bypass GDK licensing constraints and download the raw save containers directly from Microsoft's cloud servers down to your machine.

---

## ✨ Features

* 🚀 **Universal Compatibility**: Works for **ANY** Xbox Live / Game Pass game (PC, Xbox One, Xbox Series X/S).
* 🔓 **No Active Subscription Required**: Downloads cloud saves even if Game Pass has expired or you do not own the game on the Microsoft Store.
* 🔎 **Auto-Discovery via OAuth**: Authenticates with your Microsoft account via browser Device Code flow and lists every game you have ever played, along with exact Title IDs, SCIDs, and timestamps.
* 📦 **Store Catalog Resolution**: Queries Microsoft's Display Catalog API to automatically resolve Package Family Names (PFN), Application IDs, and Primary SCIDs from any Microsoft Store URL or Product ID.
* 💾 **Direct Steam/GOG/Epic Transfer**: Extracts clean, raw `.sav`, `.dat`, and binary containers ready to be loaded by Steam, GOG, or Epic Games versions.
* 🤖 **Antigravity AI Agent Skill**: Includes a complete AI agent skill (`SKILL.md`) so AI pair-programming assistants can automate cloud save recovery for users on demand.

---

## 📋 Prerequisites & Windows Developer Mode

### 1. Windows Developer Mode (Required)
To register the temporary loose developer package bridge (`Add-AppxPackage -Register`) without requiring a paid Microsoft code-signing certificate, **Windows Developer Mode must be enabled**:

* **Windows 11**: Open **Settings** $\rightarrow$ **System** $\rightarrow$ **For developers** $\rightarrow$ Toggle **Developer Mode** to **ON**.
* **Windows 10**: Open **Settings** $\rightarrow$ **Update & Security** $\rightarrow$ **For developers** $\rightarrow$ Select **Developer Mode**.
* *Alternative (PowerShell as Administrator)*:
  ```powershell
  Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock' -Name 'AllowDevelopmentWithoutDevLicense' -Value 1
  ```

> [!NOTE]
> Developer Mode allows Windows to register unpackaged application manifests in development layout. It is safe, built directly into Windows, and can be turned off whenever you finish recovering your saves.

### 2. Python 3.10+
Ensure Python 3.10 or higher is installed and on your system `PATH`.

---

## 🚀 Quick Start (Interactive Wizard)

The fastest way to recover your saves is using the interactive guided wizard:

```bash
python xbox_save_tool.py wizard
```

### Wizard Walkthrough:
1. **Login**: Open the link displayed in your terminal (e.g. `https://microsoft.com/link`) and enter the 8-letter device code to sign in with your Xbox account.
2. **Select Game**: The tool scans and lists all played games. Select your target game by number or name.
3. **Resolve Metadata**: The tool queries the Microsoft Store Catalog for the game's Package Family Name and SCID.
4. **Register Bridge**: Automatically generates and registers a developer `AppxManifest.xml` matching the title.
5. **Download Saves**: Connects to Xbox Live Cloud, downloads all save containers, generates a `manifest.json`, and creates a complete `.zip` backup archive.

---

## 💻 CLI Command Reference

The toolkit can also be scripted via standalone commands:

```bash
# 1. Discover all played games & SCIDs in your Xbox account
python xbox_save_tool.py discover

# 2. Look up Store metadata (PFN, App ID, SCID) from a Store URL or Product ID
python xbox_save_tool.py lookup <PRODUCT_ID_OR_URL>

# 3. Register package identity in Windows
python xbox_save_tool.py setup --identity "<PackageIdentityName>" \
                              --pfn "<PackageFamilyName>" \
                              --appid "<ApplicationId>"

# 4. Extract all cloud saves for a SCID
python xbox_save_tool.py extract --scid "<SCID>" --output "./ExtractedSaves"

# 5. Extract locally cached Windows Game Save (WGS) folders (optional)
python extract_wgs.py --list
python extract_wgs.py --package "<GameKeyword>"

# 6. Deploy extracted saves to target storefront with backup
python deploy_to_steam.py --source "./ExtractedSaves" --target "%LOCALAPPDATA%\<GameName>\Saved\SaveGames"
```

---

## 🔍 How to Find Your Game's SCID, Product ID, and PFN

If you prefer to run manual steps rather than the automated wizard, here is how you can find the required identifiers:

### 1. Finding Your Game's SCID (Service Configuration ID)
* **Via Account Discovery (Easiest)**:
  Run:
  ```bash
  python xbox_save_tool.py discover
  ```
  Sign in with the Microsoft account you played the game on. The tool will scan your entire Xbox title history and print a clean table containing the **Title Name**, **Title ID**, and **SCID** (UUID format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) for every game you have ever played. Full results are also saved to `history.json`.

### 2. Finding the Microsoft Store Product ID
* Open your browser and navigate to the game's page on the [Xbox / Microsoft Store](https://www.xbox.com/games/store).
* Look at the URL in your browser's address bar. It follows the pattern:
  `https://www.xbox.com/en-US/games/store/<game-title>/<12-CHAR-PRODUCT-ID>`
* The last 12 alphanumeric characters (e.g. `9XXXXXXXXXXX`) is the **Product ID**.

### 3. Resolving Package Family Name (PFN) and Application ID
* Pass either the 12-character Product ID or the full Store URL directly to the lookup command:
  ```bash
  python xbox_save_tool.py lookup <12-CHAR-PRODUCT-ID-OR-URL>
  ```
* The tool queries Microsoft's public Display Catalog API and outputs:
  * **Package Family Name (PFN)** (e.g. `<Publisher>.<GameTitle>_<PublisherId>`)
  * **Package Identity Name**
  * **Application ID** (defaults to `App` if unspecified)
  * **Primary SCID**

### 4. Finding Local Package Information (For Installed Games)
* If the game is currently or was previously installed on your PC, you can inspect installed AppX packages via PowerShell:
  ```powershell
  Get-AppxPackage *<Keyword>* | Select-Object Name, PackageFamilyName
  ```

---

## 🏗️ Architecture & How It Works

```
┌────────────────────────────────────────────────────────┐
│               Microsoft Live OAuth                     │
│  (Device Code Flow -> User Token -> XSTS Token)        │
└──────────────────────────┬─────────────────────────────┘
                           │ Authenticates Identity
                           ▼
┌────────────────────────────────────────────────────────┐
│           Xbox Title History & Catalog API             │
│  • achievements.xboxlive.com -> TitleId & SCID         │
│  • displaycatalog.mp.microsoft.com -> PFN & AppId      │
└──────────────────────────┬─────────────────────────────┘
                           │ Configures Package Identity
                           ▼
┌────────────────────────────────────────────────────────┐
│        Windows Developer Package (AppxManifest)        │
│  • Matches Target Game's PackageFamilyName             │
│  • Registered via Add-AppxPackage                      │
└──────────────────────────┬─────────────────────────────┘
                           │ WinRT Security Sandbox Granted
                           ▼
┌────────────────────────────────────────────────────────┐
│          Native C++/WinRT Cloud Save Bridge            │
│  Windows.Gaming.XboxLive.Storage.GameSaveProvider      │
│  • Bypasses GDK Licensing Check                        │
│  • Streams Raw Save Containers from Xbox Live Cloud    │
└──────────────────────────┬─────────────────────────────┘
                           │ Extracts Blobs
                           ▼
┌────────────────────────────────────────────────────────┐
│        Extracted Saves (.sav / .dat / .bin)            │
│  • ExtractedSaves/ -> Direct Steam/GOG/Epic Folders    │
│  • XboxSaves_<SCID>_Backup.zip                         │
└────────────────────────────────────────────────────────┘
```

---

## 📁 PC Save File Locations

Once extracted, copy your saves into the appropriate storefront folder:

| Engine / Platform | Typical Save Directory |
| :--- | :--- |
| **Unreal Engine 4 / 5 Games** | `%LOCALAPPDATA%\<GameName>\Saved\SaveGames\` |
| **Unity Games** | `%USERPROFILE%\AppData\LocalLow\<Developer>\<GameName>\` |
| **Windows Saved Games** | `%USERPROFILE%\Saved Games\<GameName>\` |
| **Steam UserData** | `<SteamInstallDir>\userdata\<SteamID>\<AppID>\remote\` |

---

## 🔨 Building from Source

### Prerequisites
* Windows 10 (Build 19041+) or Windows 11
* Windows Developer Mode enabled (`Settings` $\rightarrow$ `System` $\rightarrow$ `For developers` $\rightarrow$ `Developer Mode` ON)
* Visual Studio 2022 / 2026 (with C++ Desktop Development workload)
* Python 3.10+

### Build Command:
```cmd
build.bat
```
*(Or manually compile using MSVC Developer Command Prompt)*:
```cmd
cl /std:c++20 /EHsc /W4 generic_extractor.cpp /link windowsapp.lib /out:xbox_save_extractor.exe
```

---

## 🤖 Antigravity AI Agent Skill

This repository includes an **Antigravity Agent Skill** definition in `.agents/skills/xbox-cloud-save-extractor/SKILL.md`.

When using an AI coding assistant (such as Google Antigravity or Gemini Code Assist), the assistant automatically learns this skill to execute end-to-end save recoveries on your machine.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

*Disclaimer: This tool interacts with Microsoft and Xbox Live APIs using standard user OAuth authentication to download personal user save data. This project is not affiliated with, endorsed by, or associated with Microsoft or Xbox.*
