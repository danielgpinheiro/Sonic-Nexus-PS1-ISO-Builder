/*
 * Stubs for engine symbols that Script.cpp / Reader.cpp / String.cpp reference but the
 * compiler never executes (runtime-only opcodes: drawing, audio, objects, ...).
 * Generated from the linker's undefined-symbol list; regenerate if the engine changes.
 */
#include "RetroEngine.hpp"

RetroEngine Engine;

// Engine globals (defined with the exact types of their header declarations).
decltype(ActNumber) ActNumber{};
decltype(ActiveStageList) ActiveStageList{};
decltype(CameraEnabled) CameraEnabled{};
decltype(CameraStyle) CameraStyle{};
decltype(CosValue256) CosValue256{};
decltype(CosValue512) CosValue512{};
decltype(CurrentMusicTrack) CurrentMusicTrack{};
decltype(GKeyDown) GKeyDown{};
decltype(GKeyPress) GKeyPress{};
decltype(GameMenu) GameMenu{};
decltype(GlobalVariableNames) GlobalVariableNames{};
decltype(GlobalVariables) GlobalVariables{};
decltype(MilliSeconds) MilliSeconds{};
decltype(Minutes) Minutes{};
decltype(MusicVolume) MusicVolume{};
decltype(NO_GLOBALVARIABLES) NO_GLOBALVARIABLES{};
decltype(NewXBoundary1) NewXBoundary1{};
decltype(NewXBoundary2) NewXBoundary2{};
decltype(NewYBoundary1) NewYBoundary1{};
decltype(NewYBoundary2) NewYBoundary2{};
decltype(NoGlobalSFX) NoGlobalSFX{};
decltype(OBJECT_BORDER_X1) OBJECT_BORDER_X1{};
decltype(OBJECT_BORDER_X2) OBJECT_BORDER_X2{};
decltype(OBJECT_BORDER_Y1) OBJECT_BORDER_Y1{};
decltype(OBJECT_BORDER_Y2) OBJECT_BORDER_Y2{};
decltype(ObjectEntityList) ObjectEntityList{};
decltype(ObjectLoop) ObjectLoop{};
decltype(PauseEnabled) PauseEnabled{};
decltype(PlayerCBoxes) PlayerCBoxes{};
decltype(PlayerList) PlayerList{};
decltype(PlayerNo) PlayerNo{};
decltype(PlayerScriptList) PlayerScriptList{};
decltype(ScriptFrames) ScriptFrames{};
decltype(ScriptFramesNo) ScriptFramesNo{};
decltype(Seconds) Seconds{};
decltype(SinValue256) SinValue256{};
decltype(SinValue512) SinValue512{};
decltype(StageListPosition) StageListPosition{};
decltype(StageMode) StageMode{};
decltype(TextMenuSurfaceNo) TextMenuSurfaceNo{};
decltype(TilePalette) TilePalette{};
decltype(TilePalette16) TilePalette16{};
decltype(TilePalette32) TilePalette32{};
decltype(TimeEnabled) TimeEnabled{};
decltype(XBoundary1) XBoundary1{};
decltype(XBoundary2) XBoundary2{};
decltype(XScrollOffset) XScrollOffset{};
decltype(YBoundary1) YBoundary1{};
decltype(YBoundary2) YBoundary2{};
decltype(YScrollOffset) YScrollOffset{};
decltype(musInfo) musInfo{};
decltype(musicStatus) musicStatus{};
decltype(sfxChannels) sfxChannels{};
decltype(stageListCount) stageListCount{};
decltype(titleCardText) titleCardText{};
decltype(titleCardWord2) titleCardWord2{};

// Runtime-only engine functions (never called while compiling scripts).
void DrawSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int sheetID) {}
void ClearScreen(byte index) {}
void LoadPalette(const char *filePath, int startIndex, int endIndex) {}
void BoxCollision(int left, int top, int right, int bottom) {}
void DrawTextMenu(void *menu, int XPos, int YPos) {}
void DrawTintRect(int XPos, int YPos, int width, int height, byte tintID) {}
void SetMusicTrack(char *filePath, byte trackID, bool loop) {}
void SetupTextMenu(TextMenu *menu, int rowCount) {}
void BasicCollision(int left, int top, int right, int bottom) {}
int AddGraphicsFile(const char *filePath) { return 0; }
void ObjectFloorGrip(int xOffset, int yOffset, int cPath) {}
void AddTextMenuEntry(TextMenu *menu, const char *text) {}
void DrawScaledSprite(int direction, int XPos, int YPos, int pivotX, int pivotY, int scaleX, int scaleY, int width, int height, int sprX, int sprY, int sheetID) {}
void SetSfxAttributes(int sfx, int loopCount, sbyte pan) {}
void UpdateVideoFrame() {}
void DrawBlendedSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int sheetID) {}
void DrawRotatedSprite(int direction, int XPos, int YPos, int pivotX, int pivotY, int sprX, int sprY, int width, int height, int rotation, int sheetID) {}
void EditTextMenuEntry(TextMenu *menu, const char *text, int rowID) {}
void GenerateTintTable(short alpha, short a2, byte type, byte a4, byte a5, byte tableID) {}
void PlatformCollision(int left, int top, int right, int bottom) {}
void DrawScaledTintMask(int direction, int XPos, int YPos, int pivotX, int pivotY, int scaleX, int scaleY, int width, int height, int sprX, int sprY, int tintID, int sheetID) {}
void GenerateBlendTable(ushort alpha, byte type, byte a3, byte a4) {}
void RemoveGraphicsFile(const char *filePath, int sheetID) {}
void ObjectFloorCollision(int xOffset, int yOffset, int cPath) {}
void ProcessDefaultJumpAction(Player *player) {}
void ProcessDefaultAirMovement(Player *player) {}
void ProcessDefaultGravityTrue(Player *player) {}
void ProcessDefaultGravityFalse(Player *player) {}
void ProcessDefaultGroundMovement(Player *player) {}
void ProcessDefaultRollingMovement(Player *player) {}
void PlaySfx(int sfx, bool loop) {}
void SetFade(byte r, byte g, byte b, ushort a, int start, int end) {}
void PrintLog(const char *msg, ...) {}
bool PlayMusic(int track) { return false; }
// Phase 5 audio hooks the inline audio helpers (Audio.hpp) call; never executed by the compiler.
void PS1MusicStop() {}
void PS1MusicPause(bool pause) {}
void PS1SfxChannelStop(int channel) {}
