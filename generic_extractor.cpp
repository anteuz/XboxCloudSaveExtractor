#define WIN32_LEAN_AND_MEAN
#define _SILENCE_EXPERIMENTAL_COROUTINE_DEPRECATION_WARNINGS
#include <windows.h>
#include <iostream>
#include <fstream>
#include <filesystem>
#include <vector>
#include <string>
#include <sstream>

#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.System.h>
#include <winrt/Windows.Gaming.XboxLive.Storage.h>
#include <winrt/Windows.Storage.Streams.h>

#pragma comment(lib, "windowsapp.lib")

using namespace winrt;
using namespace winrt::Windows::Gaming::XboxLive::Storage;
using namespace winrt::Windows::System;
using namespace winrt::Windows::Storage::Streams;

static std::ofstream g_logFile;

static void Log(const std::string& msg) {
    std::cout << msg << std::endl;
    if (g_logFile.is_open()) {
        g_logFile << msg << std::endl;
        g_logFile.flush();
    }
}

static std::string Sanitize(const std::wstring& ws) {
    std::string s(ws.begin(), ws.end());
    for (char& c : s) {
        if (c == '\\' || c == '/' || c == ':' || c == '*' || c == '?' || c == '"' || c == '<' || c == '>' || c == '|') {
            c = '_';
        }
    }
    return s;
}

static std::wstring ToWString(const std::string& str) {
    return std::wstring(str.begin(), str.end());
}

int main(int argc, char* argv[]) {
    std::string targetScid = "";
    std::string outDirStr = "ExtractedSaves";
    std::string logFilePath = "recovery_log.txt";

    // Ensure working directory is the executable's directory
    char exePathBuf[MAX_PATH];
    if (GetModuleFileNameA(NULL, exePathBuf, MAX_PATH) > 0) {
        std::filesystem::path p(exePathBuf);
        std::filesystem::current_path(p.parent_path());
    }

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if ((arg == "--scid" || arg == "-s") && i + 1 < argc) {
            targetScid = argv[++i];
        } else if ((arg == "--out" || arg == "-o") && i + 1 < argc) {
            outDirStr = argv[++i];
        } else if ((arg == "--log" || arg == "-l") && i + 1 < argc) {
            logFilePath = argv[++i];
        }
    }

    // Fallback: check config.json in executable directory
    if (std::filesystem::exists("config.json")) {
        try {
            std::ifstream cfg("config.json");
            std::string line;
            while (std::getline(cfg, line)) {
                if (targetScid.empty()) {
                    auto pos = line.find("\"scid\"");
                    if (pos != std::string::npos) {
                        auto colon = line.find(':', pos);
                        auto firstQuote = line.find('"', colon);
                        auto secondQuote = line.find('"', firstQuote + 1);
                        if (firstQuote != std::string::npos && secondQuote != std::string::npos) {
                            targetScid = line.substr(firstQuote + 1, secondQuote - firstQuote - 1);
                        }
                    }
                }
                if (outDirStr == "ExtractedSaves") {
                    auto pos = line.find("\"output\"");
                    if (pos != std::string::npos) {
                        auto colon = line.find(':', pos);
                        auto firstQuote = line.find('"', colon);
                        auto secondQuote = line.find('"', firstQuote + 1);
                        if (firstQuote != std::string::npos && secondQuote != std::string::npos) {
                            outDirStr = line.substr(firstQuote + 1, secondQuote - firstQuote - 1);
                        }
                    }
                }
            }
        } catch (...) {}
    }

    g_logFile.open(logFilePath, std::ios::out | std::ios::trunc);

    Log("=====================================================");
    Log(" Universal Xbox Cloud Save Extractor (WinRT Bridge)");
    Log("=====================================================");

    if (targetScid.empty()) {
        Log("[-] Error: No Target SCID specified.");
        Log("    Usage: xbox_save_extractor.exe --scid <SCID> [--out <OutputDirectory>]");
        Sleep(4000);
        return 1;
    }

    Log("[*] Target SCID: " + targetScid);
    Log("[*] Output Directory: " + outDirStr);

    try {
        init_apartment();

        Log("[*] Querying active Windows User...");
        auto users = User::FindAllAsync().get();
        if (users.Size() == 0) {
            Log("[-] Error: No active Windows User found.");
            Sleep(4000);
            return 2;
        }

        User currentUser = users.GetAt(0);
        Log("[+] Active Windows User obtained: " + Sanitize(currentUser.NonRoamableId().c_str()));

        hstring scidHString = ToWString(targetScid).c_str();
        Log("[*] Connecting to Xbox Cloud Save Provider (GetSyncOnDemandForUserAsync)...");

        auto result = GameSaveProvider::GetSyncOnDemandForUserAsync(currentUser, scidHString).get();
        int status = static_cast<int>(result.Status());
        Log("[+] Provider Status Code: " + std::to_string(status));

        if (result.Status() != GameSaveErrorStatus::Ok) {
            Log("[*] Fallback: Trying GetForUserAsync...");
            result = GameSaveProvider::GetForUserAsync(currentUser, scidHString).get();
            status = static_cast<int>(result.Status());
            Log("[+] Fallback Provider Status Code: " + std::to_string(status));
        }

        if (result.Status() != GameSaveErrorStatus::Ok) {
            Log("[-] Failed connecting to GameSaveProvider (Status: " + std::to_string(status) + ").");
            Log("    Tip: Ensure your app manifest has been registered with the matching PackageFamilyName.");
            Sleep(4000);
            return 3;
        }

        GameSaveProvider provider = result.Value();
        Log("[*** SUCCESS ***] Connected to Xbox Cloud Save Provider!");

        // Enumerate containers
        Log("[*] Querying cloud save containers...");
        auto query = provider.CreateContainerInfoQuery();
        auto containerInfoRes = query.GetContainerInfoAsync().get();
        
        if (containerInfoRes.Status() != GameSaveErrorStatus::Ok) {
            Log("[-] Failed querying container info: " + std::to_string(static_cast<int>(containerInfoRes.Status())));
            Sleep(4000);
            return 4;
        }

        auto containers = containerInfoRes.Value();
        uint32_t containerCount = containers.Size();
        Log("[+] Found " + std::to_string(containerCount) + " container(s) in Xbox Live cloud.");

        std::filesystem::path outDir = outDirStr;
        std::filesystem::create_directories(outDir);

        size_t totalBlobs = 0;
        uint64_t totalBytes = 0;

        std::ofstream manifestFile(outDir / "manifest.json");
        manifestFile << "{\n  \"scid\": \"" << targetScid << "\",\n  \"containers\": [\n";

        for (uint32_t i = 0; i < containerCount; ++i) {
            auto c = containers.GetAt(i);
            std::string cName = Sanitize(c.Name().c_str());
            std::string cDisp = Sanitize(c.DisplayName().c_str());
            Log("\n-----------------------------------------------------");
            Log("Container [" + std::to_string(i + 1) + "/" + std::to_string(containerCount) + "]: " + cName + " (" + cDisp + ")");

            manifestFile << "    {\n      \"name\": \"" << cName << "\",\n      \"displayName\": \"" << cDisp << "\",\n      \"totalSize\": " << c.TotalSize() << ",\n      \"blobs\": [\n";

            GameSaveContainer container = provider.CreateContainer(c.Name());
            auto blobQuery = container.CreateBlobInfoQuery(L"");
            auto blobInfoRes = blobQuery.GetBlobInfoAsync().get();

            if (blobInfoRes.Status() == GameSaveErrorStatus::Ok) {
                auto blobs = blobInfoRes.Value();
                uint32_t blobCount = blobs.Size();
                Log("  Blobs: " + std::to_string(blobCount) + " | Total Size: " + std::to_string(c.TotalSize()) + " bytes");

                if (blobCount > 0) {
                    std::vector<hstring> blobNames;
                    for (uint32_t b = 0; b < blobCount; ++b) {
                        blobNames.push_back(blobs.GetAt(b).Name());
                    }

                    auto nameIterable = winrt::single_threaded_vector<hstring>(std::move(blobNames));
                    auto readResult = container.GetAsync(nameIterable.GetView()).get();
                    if (readResult.Status() == GameSaveErrorStatus::Ok) {
                        auto map = readResult.Value();
                        std::filesystem::path cDir = outDir / cName;
                        std::filesystem::create_directories(cDir);

                        bool firstBlob = true;
                        for (const auto& pair : map) {
                            std::string bName = Sanitize(pair.Key().c_str());
                            IBuffer buffer = pair.Value();
                            uint32_t len = buffer.Length();

                            DataReader reader = DataReader::FromBuffer(buffer);
                            std::vector<uint8_t> bytes(len);
                            reader.ReadBytes(bytes);

                            std::filesystem::path filePath = cDir / bName;
                            std::ofstream ofs(filePath, std::ios::binary);
                            if (ofs.is_open()) {
                                ofs.write(reinterpret_cast<const char*>(bytes.data()), len);
                                ofs.close();
                                Log("  [+] Saved: " + filePath.string() + " (" + std::to_string(len) + " bytes)");
                                totalBlobs++;
                                totalBytes += len;

                                if (!firstBlob) manifestFile << ",\n";
                                manifestFile << "        { \"name\": \"" << bName << "\", \"size\": " << len << " }";
                                firstBlob = false;
                            }
                        }
                    } else {
                        Log("  [-] Error reading blobs: " + std::to_string(static_cast<int>(readResult.Status())));
                    }
                }
            }
            manifestFile << "\n      ]\n    }" << (i + 1 < containerCount ? ",\n" : "\n");
        }

        manifestFile << "  ]\n}\n";
        manifestFile.close();

        Log("\n=====================================================");
        Log(" EXTRACTION COMPLETE");
        Log(" Total Containers: " + std::to_string(containerCount));
        Log(" Total Blobs:      " + std::to_string(totalBlobs));
        Log(" Total Size:       " + std::to_string(totalBytes) + " bytes");
        Log(" Destination:      " + outDir.string());
        Log(" Manifest:         " + (outDir / "manifest.json").string());
        Log("=====================================================");

    } catch (const hresult_error& ex) {
        Log("[-] WinRT HRESULT Exception: " + Sanitize(ex.message().c_str()));
    } catch (const std::exception& e) {
        Log(std::string("[-] Standard Exception: ") + e.what());
    }

    Sleep(3000);
    return 0;
}
