#ifndef AUDIO_H
#define AUDIO_H

#include <stdlib.h>

#if RETRO_PLATFORM != RETRO_PS1
#include <vorbis/vorbisfile.h>
#endif

#if RETRO_PLATFORM != RETRO_VITA && RETRO_PLATFORM != RETRO_PS1
#include "SDL.h"
#endif

// PS1 port: audio is stubbed for Phase 2. Provide the SDL/vorbis types and a
// no-op OggVorbis_File so the data structures and freeMusInfo() still compile.
#if RETRO_PLATFORM == RETRO_PS1
#include <stdint.h>
typedef int16_t Sint16;
typedef int32_t Sint32;
typedef uint8_t Uint8;
typedef uint16_t Uint16;
typedef struct { int unused; } OggVorbis_File;
#define SDL_LockAudio()   ((void)0)
#define SDL_UnlockAudio() ((void)0)
#define ov_clear(f)       ((void)0)
#endif

#define TRACK_COUNT (0x10)
#define SFX_COUNT (0x100)
#define CHANNEL_COUNT (0x4)
#define SFXDATA_COUNT (0x400000)

#define MAX_VOLUME (100)

struct TrackInfo {
    char fileName[0x40];
    bool trackLoop;
};

struct MusicPlaybackInfo {
    OggVorbis_File vorbisFile;
    int vorbBitstream;
#if RETRO_USING_SDL1
    SDL_AudioSpec spec;
#endif
#if RETRO_USING_SDL2
    SDL_AudioStream *stream;
#endif
    Sint16 *buffer;
    FileInfo fileInfo;
    bool trackLoop;
    bool loaded;
};

struct SFXInfo {
    char name[0x40];
    Sint16 *buffer;
    size_t length;
    bool loaded;
#if RETRO_PLATFORM == RETRO_PS1
    uint32_t spuAddr; // SPU-ADPCM sample in SPU RAM (build-time .vag, tools/audio/build_sfx.py)
    uint32_t rate;
#endif
};

struct ChannelInfo {
    size_t sampleLength;
    Sint16 *samplePtr;
    int sfxID;
    byte loopSFX;
    sbyte pan;
};

enum MusicStatuses {
    MUSIC_STOPPED = 0,
    MUSIC_PLAYING = 1,
    MUSIC_PAUSED  = 2,
    MUSIC_LOADING = 3,
    MUSIC_READY   = 4,
};

extern int NoGlobalSFX;
extern int NoStageSFX;

extern int MusicVolume;
extern int CurrentMusicTrack;
extern int sfxVolume;
extern int bgmVolume;
extern bool audioEnabled;

extern int nextChannelPos;
extern bool musicEnabled;
extern int musicStatus;
extern TrackInfo musicTracks[TRACK_COUNT];
extern SFXInfo sfxList[SFX_COUNT];

extern ChannelInfo sfxChannels[CHANNEL_COUNT];

extern MusicPlaybackInfo musInfo;

#if RETRO_USING_SDL1 || RETRO_USING_SDL2
extern SDL_AudioSpec audioDeviceFormat;
#endif

int InitSoundDevice();
void LoadGlobalSfx();

#if RETRO_USING_SDL1 || RETRO_USING_SDL2
void ProcessMusicStream(void *data, Sint16 *stream, int len);
void ProcessAudioPlayback(void *data, Uint8 *stream, int len);
void ProcessAudioMixing(Sint32 *dst, const Sint16 *src, int len, int volume, sbyte pan);


inline void freeMusInfo()
{
    if (musInfo.loaded) {
        SDL_LockAudio();

        if (musInfo.buffer)
            delete[] musInfo.buffer;
#if RETRO_USING_SDL2
        if (musInfo.stream)
            SDL_FreeAudioStream(musInfo.stream);
#endif
        ov_clear(&musInfo.vorbisFile);
        musInfo.buffer       = nullptr;
#if RETRO_USING_SDL2
        musInfo.stream = nullptr;
#endif
        musInfo.trackLoop    = false;
        musInfo.loaded       = false;
        musicStatus          = MUSIC_STOPPED;

        SDL_UnlockAudio();
    }
}
#else
#if RETRO_PLATFORM == RETRO_PS1
void PS1MusicStop(); // stops the CD-XA track (xa_music)
void PS1MusicPause(bool pause);
#endif
inline void ProcessMusicStream() {}
inline void ProcessAudioPlayback() {}
inline void ProcessAudioMixing() {}

inline void freeMusInfo()
{
    if (musInfo.loaded) {
        SDL_LockAudio();

        if (musInfo.buffer)
            delete[] musInfo.buffer;
        ov_clear(&musInfo.vorbisFile);
        musInfo.buffer    = nullptr;
        musInfo.trackLoop = false;
        musInfo.loaded    = false;
        musicStatus       = MUSIC_STOPPED;
#if RETRO_PLATFORM == RETRO_PS1
        PS1MusicStop();
#endif

        SDL_UnlockAudio();
    }
}
#endif

void LoadMusic(void *userdata);
void SetMusicTrack(char *filePath, byte trackID, bool loop);
bool PlayMusic(int track);
inline void StopMusic()
{
    musicStatus = MUSIC_STOPPED;
    freeMusInfo();
}

void LoadSfx(char *filePath, byte sfxID);
void PlaySfx(int sfx, bool loop);
#if RETRO_PLATFORM == RETRO_PS1
// SPU voices of the RSDK sfx channels (voices 1 and 3 have SPU capture buffers).
void PS1SfxChannelStop(int channel);
void PS1SfxReleaseStage();
void PS1SfxReleaseGlobal();
void PS1AudioUpdate(); // once per frame: frees channels whose sample ended (PC mixer semantics)
void PS1SpuDebugService(); // GDB: g_ps1SpuDumpAddr/Len -> SPU RAM copied into TileGfx
#endif
inline void StopSfx(int sfx)
{
    for (int i = 0; i < CHANNEL_COUNT; ++i) {
        if (sfxChannels[i].sfxID == sfx) {
#if RETRO_PLATFORM == RETRO_PS1
            PS1SfxChannelStop(i);
#endif
            MEM_ZERO(sfxChannels[i]);
            sfxChannels[i].sfxID = -1;
        }
    }
}
void SetSfxAttributes(int sfx, int loopCount, sbyte pan);

inline void SetMusicVolume(int volume)
{
    if (volume < 0)
        volume = 0;
    if (volume > MAX_VOLUME)
        volume = MAX_VOLUME;
    MusicVolume = volume;
}

inline void PauseSound()
{
    if (musicStatus == MUSIC_PLAYING) {
        musicStatus = MUSIC_PAUSED;
#if RETRO_PLATFORM == RETRO_PS1
        PS1MusicPause(true);
#endif
    }
}

inline void ResumeSound()
{
    if (musicStatus == MUSIC_PAUSED) {
        musicStatus = MUSIC_PLAYING;
#if RETRO_PLATFORM == RETRO_PS1
        PS1MusicPause(false);
#endif
    }
}


inline void StopAllSfx()
{
    for (int i = 0; i < CHANNEL_COUNT; ++i) {
#if RETRO_PLATFORM == RETRO_PS1
        PS1SfxChannelStop(i);
#endif
        sfxChannels[i].sfxID = -1;
    }
}
inline void ReleaseGlobalSfx()
{
    StopAllSfx();
    for (int i = NoGlobalSFX - 1; i >= 0; --i) {
        if (sfxList[i].loaded) {
            StrCopy(sfxList[i].name, "");
            free(sfxList[i].buffer);
            sfxList[i].length = 0;
            sfxList[i].loaded = false;
        }
    }
    NoGlobalSFX = 0;
#if RETRO_PLATFORM == RETRO_PS1
    PS1SfxReleaseGlobal();
#endif
}
inline void ReleaseStageSfx()
{
    for (int i = NoStageSFX + NoGlobalSFX; i >= NoGlobalSFX; --i) {
        if (sfxList[i].loaded) {
            StrCopy(sfxList[i].name, "");
            free(sfxList[i].buffer);
            sfxList[i].length = 0;
            sfxList[i].loaded = false;
        }
    }
    NoStageSFX = 0;
#if RETRO_PLATFORM == RETRO_PS1
    PS1SfxReleaseStage();
#endif
}

inline void ReleaseSoundDevice()
{
    StopMusic();
    StopAllSfx();
    ReleaseStageSfx();
    ReleaseGlobalSfx();
}

#endif // !AUDIO_H
