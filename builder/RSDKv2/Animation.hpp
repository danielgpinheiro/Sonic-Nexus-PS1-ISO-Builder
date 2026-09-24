#ifndef ANIMATION_H
#define ANIMATION_H

#define ANIFILE_COUNT (0x100)
#if RETRO_PLATFORM == RETRO_PS1
#define ANIMATION_COUNT (0x200)
#define SPRITEFRAME_COUNT (0x800)
#else
#define ANIMATION_COUNT (0x400)
#define SPRITEFRAME_COUNT (0x1000)
#endif

#define HITBOX_COUNT (0x20)
#define HITBOX_DIR_COUNT (0x8)

struct SpriteFrame {
    int sprX;
    int sprY;
    int width;
    int height;
    int pivotX;
    int pivotY;
    byte sheetID;
    byte hitboxID;
};

struct SpriteAnimation {
    byte frameCount;
    byte speed;
    byte loopPoint;
    SpriteFrame* frames;
};

struct Hitbox {
    sbyte left[HITBOX_DIR_COUNT];
    sbyte top[HITBOX_DIR_COUNT];
    sbyte right[HITBOX_DIR_COUNT];
    sbyte bottom[HITBOX_DIR_COUNT];
};

extern SpriteFrame ScriptFrames[SPRITEFRAME_COUNT];
extern int ScriptFramesNo;

extern SpriteFrame animFrames[SPRITEFRAME_COUNT];
extern Hitbox PlayerCBoxes[HITBOX_COUNT];

void LoadPlayerAnimation(const char *filePath, int playerID);
void ClearAnimationData();

#endif // !ANIMATION_H
