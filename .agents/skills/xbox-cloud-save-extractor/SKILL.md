---
name: xbox-cloud-save-extractor
description: >-
  Extract and recover Xbox Game Pass / Xbox Live cloud saves for ANY PC or Console game directly
  from Microsoft's cloud servers without requiring an active Game Pass subscription or game installation.
  Use when the user wants to recover saves, transfer Xbox saves to Steam/GOG/Epic, or resolve Xbox cloud sync errors.
---

# Xbox Cloud Save Recovery & Migration Skill

This skill provides an end-to-end guide and automated toolkit for recovering and downloading Xbox Live / Game Pass cloud saves for **any game**, even after Game Pass has expired or the game has been uninstalled.

---

## 💡 How It Works & Architecture

Microsoft's Xbox Live architecture protects game saves behind two layers:
1. **User Identity**: Proven via Microsoft OAuth (Device Code flow) $\rightarrow$ User Token $\rightarrow$ XSTS Token.
2. **Title Security Boundary**: Microsoft's cloud save servers (`GSLS` / `Connected Storage`) reject direct REST calls from unauthorized clients (`403 Forbidden` / `400 Bad Request`).
3. **The Solution (WinRT Native OS Bridge)**: Windows 10/11 includes the native `Windows.Gaming.XboxLive.Storage.GameSaveProvider` Windows Runtime (WinRT) subsystem. When an application runs under a registered developer `AppxManifest.xml` matching the game's **Package Family Name (PFN)**, Windows authorizes the process and syncs down the cloud saves directly from Microsoft's cloud into raw save containers without requiring game licenses or GDK signing!

---

## 🚀 Quick Start: Universal CLI Tool

An all-in-one CLI tool `xbox_save_tool.py` is included in this repository:

```bash
# 1. Interactive Guided Wizard (Recommended)
python xbox_save_tool.py wizard

# 2. Discover all played games & SCIDs in your Xbox account
python xbox_save_tool.py discover

# 3. Look up Store metadata (PFN, App ID, SCID) from a Store URL or Product ID
python xbox_save_tool.py lookup 9N3D6V4N58JR

# 4. Register package identity in Windows
python xbox_save_tool.py setup --identity "GSCGameWorld.S.T.A.L.K.E.R.2HeartofChernobyl" --pfn "GSCGameWorld.S.T.A.L.K.E.R.2HeartofChernobyl_6fr1t1rwfarwt" --appid "Stalker2RedirectionApp"

# 5. Extract all cloud saves for a SCID
python xbox_save_tool.py extract --scid "00000000-0000-0000-0000-00007782504a" --output "./ExtractedSaves"
```

---

## 🛠️ Step-by-Step Manual Procedure

### Step 1: Discover Account Games & SCIDs
Authenticate with Microsoft Live OAuth Device Code flow and query Xbox Live Achievements/Title History:

* **OAuth Endpoint**: `https://login.live.com/oauth20_connect.srf` (`client_id=000000004C12AE6F`, `scope=service::user.auth.xboxlive.com::MBI_SSL`)
* **User Authentication**: `https://user.auth.xboxlive.com/user/authenticate`
* **XSTS Token (`http://xboxlive.com`)**: `https://xsts.auth.xboxlive.com/xsts/authorize`
* **Title History Endpoint**:
  ```http
  GET https://achievements.xboxlive.com/users/xuid({xuid})/history/titles?maxItems=100
  Authorization: XBL3.0 x={uhs};{xsts_token}
  x-xbl-contract-version: 2
  ```
* **Extract**: `name`, `titleId` (Decimal & Hex), and `serviceConfigId` (SCID).

---

### Step 2: Query Store Catalog for Package Family Name (PFN)
Query the Microsoft Display Catalog API using the game's 12-character Product ID (found in the `xbox.com/games/store` URL):

```http
GET https://displaycatalog.mp.microsoft.com/v7.0/products/{productId}?market=US&languages=en-US
```

From the response JSON, extract:
* `Properties.PackageFamilyName` (e.g. `GSCGameWorld.S.T.A.L.K.E.R.2HeartofChernobyl_6fr1t1rwfarwt`)
* `Properties.PackageIdentityName` (e.g. `GSCGameWorld.S.T.A.L.K.E.R.2HeartofChernobyl`)
* `Properties.ApplicationId` (e.g. `Stalker2RedirectionApp` or `App`)
* `Properties.PrimaryServiceConfigId` (SCID)

---

### Step 3: Register Developer AppxManifest
Enable **Developer Mode** in Windows (`Settings` $\rightarrow$ `System` $\rightarrow$ `For developers` $\rightarrow$ `Developer Mode` ON).

Create `AppxManifest.xml` matching the game's identity:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
  <Identity Name="<PackageIdentityName>"
            ProcessorArchitecture="x64"
            Publisher="CN=Developer, O=Developer, C=US"
            Version="1.0.0.0" />
  <Properties>
    <DisplayName>Cloud Save Recovery</DisplayName>
    <PublisherDisplayName>Recovery Tool</PublisherDisplayName>
    <Logo>Assets\StoreLogo.png</Logo>
  </Properties>
  <Resources><Resource Language="en-US" /></Resources>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Capabilities><rescap:Capability Name="runFullTrust" /></Capabilities>
  <Applications>
    <Application Id="<ApplicationId>"
                 Executable="xbox_save_extractor.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Save Recovery"
                          Description="Xbox Cloud Save Recovery"
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\Logo.png"
                          Square44x44Logo="Assets\SmallLogo.png" />
    </Application>
  </Applications>
</Package>
```

Register the package:
```powershell
Add-AppxPackage -Register ".\AppxManifest.xml"
```

---

### Step 4: Extract Saves via C++/WinRT Bridge
Compile and run the generic C++/WinRT save extractor:

```cpp
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.System.h>
#include <winrt/Windows.Gaming.XboxLive.Storage.h>
#include <winrt/Windows.Storage.Streams.h>

using namespace winrt;
using namespace winrt::Windows::Gaming::XboxLive::Storage;
using namespace winrt::Windows::System;

int main() {
    init_apartment();
    auto users = User::FindAllAsync().get();
    User currentUser = users.GetAt(0);
    
    hstring scid = L"00000000-0000-0000-0000-00007782504a";
    auto result = GameSaveProvider::GetForUserAsync(currentUser, scid).get();
    if (result.Status() == GameSaveErrorStatus::Ok) {
        GameSaveProvider provider = result.Value();
        auto query = provider.CreateContainerInfoQuery();
        auto containers = query.GetContainerInfoAsync().get().Value();
        
        for (auto c : containers) {
            GameSaveContainer container = provider.CreateContainer(c.Name());
            auto blobs = container.CreateBlobInfoQuery(L"").GetBlobInfoAsync().get().Value();
            // Read and save blob bytes...
        }
    }
}
```

Compile with MSVC:
```cmd
cl /std:c++20 /EHsc /W4 generic_extractor.cpp /link windowsapp.lib /out:xbox_save_extractor.exe
```

Run extraction:
```cmd
xbox_save_extractor.exe --scid "<SCID>" --out "./ExtractedSaves"
```

---

### Step 5: Transfer to Steam / GOG / Epic Save Locations
Common PC save paths for extracted Unreal Engine & standard titles:

* **Unreal Engine 4/5 Titles (e.g. S.T.A.L.K.E.R. 2)**:
  `%LOCALAPPDATA%\<GameName>\Saved\SaveGames\`
* **Unity Titles**:
  `%USERPROFILE%\AppData\LocalLow\<Developer>\<GameName>\`
* **Direct Save Games Directory**:
  `%USERPROFILE%\Saved Games\<GameName>\`

---

## 🔍 Troubleshooting Guide

| Issue / Error Code | Cause | Fix |
| :--- | :--- | :--- |
| **`0x89245115` / `E_GAMEUSER_NO_DEFAULT_USER`** | Unpackaged Win32 console app calling GDK without parent HWND window. | Use the C++/WinRT `GameSaveProvider` bridge or provide a Win32 message loop window. |
| **`0x80070002` / `0x8924520B`** | GDK checking for local loose license signatures. | WinRT bypasses GDK licensing entirely when registered via `AppxManifest.xml`. |
| **`400 Bad Request` on XSTS** | Querying invalid RelyingParty without Device Token. | Use `http://xboxlive.com` for title queries and let WinRT handle storage RPC. |
| **`404 Not Found` on titlestorage** | Game uses Connected Storage (`XGameSave`), not Title Storage. | Connected storage containers are managed via `GameSaveProvider`. |
| **Camera spinning / Gamepad stuck in UI** | Flight sticks (HOTAS), rudder pedals, or virtual joysticks outputting resting axis signals. | Unplug HOTAS/pedals or add `bEnableDirectInput=False` & `bEnableRawInput=False` to `Engine.ini`. |
