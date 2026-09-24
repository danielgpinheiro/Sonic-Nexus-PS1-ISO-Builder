#ifndef DRAWING_H
#define DRAWING_H

#define SPRITESHEETS_MAX (16)
#define SURFACE_MAX      (24)
#if RETRO_PLATFORM == RETRO_PS1
// PS1: sprites live in VRAM only (per-stage atlas, ps1/sprite_atlas.*); GraphicData is a
// stub kept so the (unreachable) software-renderer code still links.
#define GFXDATA_MAX      (0x10)
#else
#define GFXDATA_MAX      (0x400000)
#endif

#define DRAWLAYER_COUNT (0x7)

#if RETRO_PLATFORM == RETRO_PS1
namespace psyqo {
class GPU;
}
extern psyqo::GPU *g_ps1GPU;
#endif

enum FlipFlags { FLIP_NONE, FLIP_X, FLIP_Y, FLIP_XY };
enum InkFlags { INK_NONE, INK_BLEND, INK_TINT };
enum DrawFXFlags { FX_SCALE, FX_ROTATE, FX_INK, FX_TINT };

struct DrawListEntry {
    int entityRefs[ENTITY_COUNT];
    int listSize;
};

struct GFXSurface {
    char fileName[0x40];
    int height;
    int width;
    int dataPosition;
#if RETRO_PLATFORM == RETRO_PS1
    int vramPageX; // texture page X (N*64 halfwords); -1 = not uploaded
    int vramPageY; // texture page Y (N*256 lines)
    bool vramDirect15; // 15-bit texture written straight to VRAM (FMV): no CLUT, no GraphicData
    short atlasSheet;  // sheet index in the current stage atlas, -1 = none (not drawn)
#endif
};

extern int SCREEN_XSIZE;
extern int SCREEN_CENTERX;

#if RETRO_PLATFORM != RETRO_PS1
extern byte BlendLookupTable[0x100 * 0x100];
#endif

extern byte TintLookupTable1[0x100];
extern byte TintLookupTable2[0x100];
extern byte TintLookupTable3[0x100];
extern byte TintLookupTable4[0x100];

extern DrawListEntry ObjectDrawOrderList[DRAWLAYER_COUNT];

extern int GfxDataPosition;
extern GFXSurface GfxSurface[SURFACE_MAX];
extern byte GraphicData[GFXDATA_MAX];

int InitRenderDevice();
void FlipScreen();
#if RETRO_PLATFORM == RETRO_PS1
void PS1UploadPalette();
void PS1FinalizePalette(); // FlipScreen: end-of-frame palette into the chained CLUT uploads
// Packed per-chunk-tile word for the GPU tile renderer, stored in StageTiles.gfxDataPos:
// bits 0-15 = u | v << 8 in its tile page, 16-17 page, 18-19 FLIP_*, bit 20 plane, bit 21 non-empty.
uint32_t PS1TileVisual(int tileIndex, int direction, int visualPlane);
void PS1ResetSpriteSurfaces(); // stage change: forget VRAM placement of every surface
void PS1InvalidateTileSet();   // stage change: the new 16x16Tiles.vram is uploaded on the next frame
void PS1BindSheet(int sheetID); // bind a named surface to the current stage atlas
void PS1BindAllSheets();        // after an atlas load (player sheets persist across stages)
bool PS1AllocDirectSurface(int sheetID); // 15-bit surface: the atlas' reserved FMV page
#endif
void ReleaseRenderDevice();

void ClearScreen(byte index);

inline void ClearGraphicsData() {
    for (int i = 0; i < SURFACE_MAX; ++i) StrCopy(GfxSurface[i].fileName, "");
    GfxDataPosition = 0;
#if !RETRO_USE_ORIGINAL_CODE
    MEM_ZERO(GfxSurface);
#endif
#if RETRO_PLATFORM == RETRO_PS1
    PS1ResetSpriteSurfaces();
#endif
}

void SetScreenSize(int width, int lineSize);

void GenerateBlendTable(ushort alpha, byte type, byte a3, byte a4);
void GenerateTintTable(short alpha, short a2, byte type, byte a4, byte a5, byte tableID);

// Layer Drawing
void DrawObjectList(int layer);
void DrawStageGfx();

// TileLayer Drawing
void DrawHLineScrollLayer(int layerID);
void DrawVLineScrollLayer(int layerID);
void Draw3DCloudLayer(int layerID);

// Shape Drawing
void DrawTintRect(int XPos, int YPos, int width, int height, byte tintID);
void DrawScaledTintMask(int direction, int XPos, int YPos, int pivotX, int pivotY, int scaleX, int scaleY, int width, int height, int sprX, int sprY,
                        int tintID, int sheetID);

// Sprite Drawing
void DrawSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int sheetID);
void DrawScaledSprite(int direction, int XPos, int YPos, int pivotX, int pivotY, int scaleX, int scaleY, int width, int height, int sprX, int sprY,
                      int sheetID);
void DrawRotatedSprite(int direction, int XPos, int YPos, int pivotX, int pivotY, int sprX, int sprY, int width, int height, int rotation,
                       int sheetID);
void DrawBlendedSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int sheetID);

// Text Menus
void DrawTextMenuEntry(void *menu, int rowID, int XPos, int YPos, int textHighlight);
void DrawBlendedTextMenuEntry(void *menu, int rowID, int XPos, int YPos, int textHighlight);
void DrawStageTextEntry(void *menu, int rowID, int XPos, int YPos, int textHighlight);
void DrawTextMenu(void *menu, int XPos, int YPos);

#endif // !DRAWING_H
