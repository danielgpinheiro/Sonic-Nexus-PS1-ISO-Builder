#ifndef VIDEO_H
#define VIDEO_H

extern int CurrentVideoFrame;
extern int VideoFrameCount;
extern int VideoWidth;
extern int VideoHeight;
extern int VideoSurface;
extern int VideoFilePos;
extern bool VideoPlaying;

#if RETRO_PLATFORM == RETRO_PS1
void PS1UpdateVideoTexture(); // once per game frame, outside the DMA chain (main.cpp)
void PS1StopVideo();          // close the stream + free the FMV heap (stage change, CD reads)
#endif

void UpdateVideoFrame();

#endif // !VIDEO_H
