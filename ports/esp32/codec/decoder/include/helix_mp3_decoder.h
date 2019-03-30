/*
 * helix_mp3_decoder.h
 *
 *  
 *      
 */
#ifndef __helix_mp3_decoder_h__
#define __helix_mp3_decoder_h__

#define HELIX_DECODER_TASK_STACK_DEPTH 3200
#include "mp3dec.h"

typedef struct{
    HMP3Decoder HMP3Decoder;
    MP3FrameInfo mp3FrameInfo;
    int samplerate;
    short *output;
    unsigned char *readBuf;
    int supply_bytes;
    int bytesleft;
    unsigned char *readPtr;
}mp3_decode_t;

mp3_decode_t *get_mp3_decode_handle(void);
void set_mp3_decode_handle(mp3_decode_t *Decoder);
mp3_decode_t *mp3_decode_init();
int mp3_file_data_proccess(const char *buf, size_t len);
void mp3_decoder_task(void *pvParameters);

#endif //__helix_mp3_decoder_h__
