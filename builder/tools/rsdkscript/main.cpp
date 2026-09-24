/*
 * rsdkscript — host-side RetroScript v2 compiler for the RSDKv2 PS1 port.
 *
 * Runs the engine's own ParseScriptFile (RSDKv2/Script.cpp, built for the Mac with the
 * PS1 configuration) exactly the way LoadStageFiles does on the console, once per stage
 * folder listed in GameConfig.bin, and writes the compiled state as
 *   <out>/<StageFolder>.bin
 * which the PS1 build loads instead of parsing .txt scripts at runtime (golden rule).
 *
 * File format "RSB2" (all little-endian, PS1 memory layout):
 *   u32 magic 'RSB2', u32 version (1)
 *   u32 ScriptDataPos, u32 JumpTableDataPos
 *   i32 ScriptData[ScriptDataPos], i32 JumpTableData[JumpTableDataPos]
 *   ObjectScript[OBJECT_COUNT], 40 bytes each: u8 frameCount, u8 spriteSheetID, u16 0,
 *       4 x {i32 scriptCodePtr, i32 jumpTablePtr} (main, playerInteraction, draw, startup),
 *       u32 0 (frameStartPtr, set at runtime)
 *   PlayerScript[PLAYER_COUNT]: i32 mainCode, i32 mainJump, i32 stateCode[256], i32 stateJump[256]
 *
 * Usage: rsdkscript <root containing Data/> <output dir> [--legacy-ssz FILE] [--manifest DIR]
 *
 * --manifest DIR also writes DIR/<StageFolder>.txt for the sprite atlas builder
 * (tools/atlas/build_atlas.py): one "script <path under Data/Scripts/>" line per script in
 * load order (globals, stage, players) and one "ani <file under Data/Animations/>" line per
 * player animation file.
 */
#include "RetroEngine.hpp"

#include <set>
#include <string>
#include <vector>

#include <sys/stat.h>
#include <unistd.h>

static std::string readStr() {
    byte len = 0;
    FileRead(&len, 1);
    char buf[0x100];
    FileRead(buf, len);
    buf[len] = 0;
    return buf;
}

struct GameConfigInfo {
    std::vector<std::string> globalScripts;
    std::vector<std::string> playerAnims;
    std::vector<std::string> playerScripts;
    std::vector<std::string> stageFolders; // unique, in list order
};

static bool readGameConfig(GameConfigInfo &gc) {
    FileInfo info;
    if (!LoadFile("Data/Game/GameConfig.bin", &info))
        return false;
    readStr(); // title
    readStr(); // "Data"
    readStr(); // description
    byte count = 0;
    FileRead(&count, 1);
    for (int i = 0; i < count; ++i) gc.globalScripts.push_back(readStr());
    FileRead(&count, 1); // global variables: names are needed by the parser
    NO_GLOBALVARIABLES = count;
    for (int v = 0; v < count; ++v) {
        std::string name = readStr();
        StrCopy(GlobalVariableNames[v], name.c_str());
        byte val[4];
        FileRead(val, 4);
    }
    FileRead(&count, 1); // SFX
    for (int i = 0; i < count; ++i) readStr();
    FileRead(&count, 1); // players: anim, script, name
    for (int p = 0; p < count; ++p) {
        gc.playerAnims.push_back(readStr());
        gc.playerScripts.push_back(readStr());
        readStr();
    }
    std::set<std::string> seen;
    for (int c = 0; c < 4; ++c) {
        byte n = 0;
        FileRead(&n, 1);
        for (int s = 0; s < n; ++s) {
            std::string folder = readStr();
            readStr(); // id
            readStr(); // name
            byte mode;
            FileRead(&mode, 1);
            if (seen.insert(folder).second)
                gc.stageFolders.push_back(folder);
        }
    }
    CloseFile();
    return true;
}

// Mirrors the script part of LoadStageFiles (RSDKv2/Scene.cpp).
static std::vector<std::string> s_stageScripts; // scripts of the last compiled stage, load order

static bool compileStage(const GameConfigInfo &gc, const std::string &folder, int *parsedCount) {
    s_stageScripts.clear();
    ClearScriptData();
    int scriptID = 2;
    std::string cfg = "Data/Stages/" + folder + "/StageConfig.bin";
    FileInfo info;
    bool loadGlobals = false;
    if (!LoadFile(cfg.c_str(), &info))
        return false;
    FileRead(&loadGlobals, 1);
    CloseFile();
    int parsed = 0;
    if (loadGlobals) {
        for (const auto &s : gc.globalScripts) {
            s_stageScripts.push_back(s);
            ParseScriptFile((char *)s.c_str(), scriptID++);
            ++parsed;
        }
    }
    if (LoadFile(cfg.c_str(), &info)) {
        byte b;
        FileRead(&b, 1); // loadGlobals
        for (int i = 96; i < 128; ++i) {
            byte clr[3];
            FileRead(clr, 3);
        }
        byte n = 0;
        FileRead(&n, 1);
        std::vector<std::string> stageScripts;
        for (int i = 0; i < n; ++i) stageScripts.push_back(readStr());
        CloseFile();
        for (int i = 0; i < n; ++i) {
            s_stageScripts.push_back(stageScripts[i]);
            ParseScriptFile((char *)stageScripts[i].c_str(), scriptID + i);
            ++parsed;
        }
    }
    for (int p = 0; p < PLAYER_COUNT && p < (int)gc.playerScripts.size(); ++p) {
        if (!gc.playerScripts[p].empty()) {
            s_stageScripts.push_back(gc.playerScripts[p]);
            ParseScriptFile((char *)gc.playerScripts[p].c_str(), p);
            ++parsed;
        }
    }
    *parsedCount = parsed;
    return true;
}

static void put32(FILE *f, uint32_t v) {
    uint8_t b[4] = { (uint8_t)v, (uint8_t)(v >> 8), (uint8_t)(v >> 16), (uint8_t)(v >> 24) };
    fwrite(b, 1, 4, f);
}

static void writeObjectScripts(FILE *f) {
    for (int o = 0; o < OBJECT_COUNT; ++o) {
        const ObjectScript &s = ObjectScriptList[o];
        uint8_t hdr[4] = { s.frameCount, s.spriteSheetID, 0, 0 };
        fwrite(hdr, 1, 4, f);
        const ScriptPtr *subs[4] = { &s.subMain, &s.subPlayerInteraction, &s.subDraw, &s.subStartup };
        for (auto *sp : subs) {
            put32(f, (uint32_t)sp->scriptCodePtr);
            put32(f, (uint32_t)sp->jumpTablePtr);
        }
        put32(f, 0); // frameStartPtr
    }
}

static bool writeBytecode(const std::string &path) {
    FILE *f = ::fopen(path.c_str(), "wb");
    if (!f)
        return false;
    put32(f, 0x32425352); // "RSB2"
    put32(f, 1);
    put32(f, ScriptDataPos);
    put32(f, JumpTableDataPos);
    for (int i = 0; i < ScriptDataPos; ++i) put32(f, (uint32_t)ScriptData[i]);
    for (int i = 0; i < JumpTableDataPos; ++i) put32(f, (uint32_t)JumpTableData[i]);
    writeObjectScripts(f);
    for (int p = 0; p < PLAYER_COUNT; ++p) {
        const PlayerScript &ps = PlayerScriptList[p];
        put32(f, ps.scriptCodePtr_PlayerMain);
        put32(f, ps.jumpTablePtr_PlayerMain);
        for (int s = 0; s < 256; ++s) put32(f, ps.scriptCodePtr_PlayerState[s]);
        for (int s = 0; s < 256; ++s) put32(f, ps.jumpTablePtr_PlayerState[s]);
    }
    ::fclose(f);
    return true;
}

// Compare the current compiled state with a legacy runtime dump (the old Precompiled.bin:
// ScriptDataPos, JumpTableDataPos, ScriptData, JumpTableData, ObjectScript[256] x 40 B).
static int compareLegacy(const char *path) {
    FILE *f = ::fopen(path, "rb");
    if (!f) {
        printf("  legacy: cannot open %s\n", path);
        return 1;
    }
    std::vector<uint8_t> d;
    uint8_t buf[4096];
    size_t r;
    while ((r = ::fread(buf, 1, sizeof(buf), f)) > 0) d.insert(d.end(), buf, buf + r);
    ::fclose(f);
    auto rd = [&](size_t off) { return (int32_t)(d[off] | d[off + 1] << 8 | d[off + 2] << 16 | (uint32_t)d[off + 3] << 24); };
    int sdp = rd(0), jtp = rd(4);
    printf("  legacy: ScriptDataPos %d (tool %d), JumpTableDataPos %d (tool %d)\n", sdp, ScriptDataPos, jtp, JumpTableDataPos);
    int diffs = 0;
    size_t off = 8;
    for (int i = 0; i < sdp; ++i, off += 4)
        if (i >= ScriptDataPos || rd(off) != ScriptData[i]) diffs++;
    int sdDiff = diffs;
    for (int i = 0; i < jtp; ++i, off += 4)
        if (i >= JumpTableDataPos || rd(off) != JumpTableData[i]) diffs++;
    int jtDiff = diffs - sdDiff;
    int objDiff = 0;
    for (int o = 0; o < OBJECT_COUNT; ++o, off += 40) {
        const ObjectScript &s = ObjectScriptList[o];
        const ScriptPtr *subs[4] = { &s.subMain, &s.subPlayerInteraction, &s.subDraw, &s.subStartup };
        bool bad = d[off] != s.frameCount || d[off + 1] != s.spriteSheetID;
        for (int k = 0; k < 4; ++k)
            bad |= rd(off + 4 + k * 8) != subs[k]->scriptCodePtr || rd(off + 8 + k * 8) != subs[k]->jumpTablePtr;
        objDiff += bad;
    }
    printf("  legacy: ScriptData diffs %d, JumpTable diffs %d, ObjectScript entries differing %d (bytes %zu/%zu)\n",
           sdDiff, jtDiff, objDiff, off, d.size());
    return (sdp == ScriptDataPos && jtp == JumpTableDataPos && diffs == 0 && objDiff == 0 && off == d.size()) ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <root containing Data/> <output dir> [--legacy-ssz FILE]\n", argv[0]);
        return 2;
    }
    const char *legacy = nullptr;
    std::string manifestDir;
    for (int a = 3; a + 1 < argc; a += 2) {
        if (!strcmp(argv[a], "--legacy-ssz"))
            legacy = argv[a + 1];
        else if (!strcmp(argv[a], "--manifest"))
            manifestDir = argv[a + 1];
    }
    std::string outDir = argv[2];
    char cwd[1024];
    if (outDir[0] != '/' && getcwd(cwd, sizeof(cwd)))
        outDir = std::string(cwd) + "/" + outDir;
    if (!manifestDir.empty() && manifestDir[0] != '/' && getcwd(cwd, sizeof(cwd)))
        manifestDir = std::string(cwd) + "/" + manifestDir;
    if (!manifestDir.empty())
        mkdir(manifestDir.c_str(), 0755);
    if (chdir(argv[1]) != 0) {
        perror(argv[1]);
        return 2;
    }
    mkdir(outDir.c_str(), 0755);
    Engine.UseBinFile = false;

    GameConfigInfo gc;
    if (!readGameConfig(gc)) {
        fprintf(stderr, "cannot read Data/Game/GameConfig.bin\n");
        return 1;
    }
    printf("GameConfig: %zu global scripts, %d global vars, %zu player scripts, %zu stage folders\n",
           gc.globalScripts.size(), NO_GLOBALVARIABLES, gc.playerScripts.size(), gc.stageFolders.size());
    int rc = 0;
    for (const auto &folder : gc.stageFolders) {
        int parsed = 0;
        if (!compileStage(gc, folder, &parsed)) {
            printf("%-10s  (no StageConfig.bin, skipped)\n", folder.c_str());
            continue;
        }
        std::string out = outDir + "/" + folder + ".bin";
        if (!writeBytecode(out)) {
            fprintf(stderr, "cannot write %s\n", out.c_str());
            return 1;
        }
        printf("%-10s  %2d scripts  ScriptData %5d ints  JumpTable %4d ints  -> %s\n", folder.c_str(), parsed,
               ScriptDataPos, JumpTableDataPos, out.c_str());
        if (legacy && folder == "SSZ")
            rc |= compareLegacy(legacy);
        if (!manifestDir.empty()) {
            std::string mpath = manifestDir + "/" + folder + ".txt";
            FILE *m = ::fopen(mpath.c_str(), "w");
            if (!m) {
                fprintf(stderr, "cannot write %s\n", mpath.c_str());
                return 1;
            }
            for (const auto &sc : s_stageScripts) fprintf(m, "script %s\n", sc.c_str());
            for (const auto &an : gc.playerAnims) fprintf(m, "ani %s\n", an.c_str());
            ::fclose(m);
        }
    }
    return rc;
}
