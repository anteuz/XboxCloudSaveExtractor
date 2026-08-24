#include <iostream>
#include <string>
#include <cassert>
#include <fstream>
#include <filesystem>

// Logic under test extracted from generic_extractor.cpp
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

void TestSanitize() {
    assert(Sanitize(L"normal_filename.sfs") == "normal_filename.sfs");
    assert(Sanitize(L"path\\with/all:special*chars?and\"quotes<and>pipes|") == "path_with_all_special_chars_and_quotes_and_pipes_");
    assert(Sanitize(L"") == "");
    std::cout << "[+] TestSanitize passed." << std::endl;
}

void TestToWString() {
    assert(ToWString("hello world") == L"hello world");
    assert(ToWString("") == L"");
    std::cout << "[+] TestToWString passed." << std::endl;
}

void TestConfigParsing() {
    std::string testCfg = "test_config.json";
    std::ofstream ofs(testCfg);
    ofs << "{\n  \"scid\": \"00000000-0000-0000-0000-000012345678\",\n  \"output\": \"CustomOutDir\"\n}\n";
    ofs.close();

    std::string targetScid = "";
    std::string outDirStr = "ExtractedSaves";

    if (std::filesystem::exists(testCfg)) {
        std::ifstream cfg(testCfg);
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
    }

    assert(targetScid == "00000000-0000-0000-0000-000012345678");
    assert(outDirStr == "CustomOutDir");
    std::filesystem::remove(testCfg);
    std::cout << "[+] TestConfigParsing passed." << std::endl;
}

int main() {
    std::cout << "Running C++ Unit Tests..." << std::endl;
    TestSanitize();
    TestToWString();
    TestConfigParsing();
    std::cout << "[*** ALL C++ TESTS PASSED ***]" << std::endl;
    return 0;
}

