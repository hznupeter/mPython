/*
 * audio_player.h
 *
 *  Created on: 12.03.2017
 *      Author: michaelboeckling
 */

#ifndef INCLUDE_AUDIO_PLAYER_H_
#define INCLUDE_AUDIO_PLAYER_H_

#include <sys/types.h>
#include "audio_renderer.h"
#include "freertos/ringbuf.h"
#include "freertos/semphr.h"
#include "py/reader.h"
#include "esp_http_client.h"
#include "http_client.h"
// #include "freertos/event_groups.h"

#define BIT_0    ( 1 << 0 )
#define BIT_1    ( 1 << 1 )

#define RINGBUF_SIZE 5000
#define FILE_DATA_READ_LEN 100
#define MIN_VOL_OFFSET -25 //50

// int audio_stream_consumer(const char *recv_buf, ssize_t bytes_read, void *user_data);
typedef enum {
    UNKNOW_TYPE = 0,
    LOCAL_TYPE, 
    WEB_TYPE
} audio_type_t;

typedef enum {
    UNINITIALIZED, INITIALIZED, RUNNING, STOPPED, PAUSED
} player_status_t, component_status_t;

typedef enum {
    CMD_NONE, CMD_START, CMD_STOP, CMD_PAUSE,
} player_command_t;

typedef enum {
    BUF_PREF_FAST, BUF_PREF_SAFE
} buffer_pref_t;

typedef enum
{
    MIME_UNKNOWN = 1, OCTET_STREAM, AUDIO_AAC, AUDIO_MP4, AUDIO_MPEG, AUDIO_TEXT
} content_type_t;

typedef struct {
    content_type_t content_type;
    bool eof;
} media_stream_t;

#define PLAYER_DEFAULT(){                     \
        .command  = CMD_NONE,                  \
        .player_status = RUNNING,        \
        .buffer_pref = BUF_PREF_SAFE,          \
        .buf_handle = NULL,                    \
        .ringbuf_size = RINGBUF_SIZE,          \
        .ringbuf_sem = NULL,                   \
        .play_begin = true,                    \
        .mp3_get_tag = true,                   \
        .wait_first_read_full = true,          \
        .http_head = NULL,                     \
        .http_body = NULL,                     \
        .set_http_head = fasle,                \
        .has_http_body = fasle,                \
        .media_stream = {                      \
            .content_type = MIME_UNKNOWN,      \
            .eof = false,                      \
        },                                     \
};

typedef struct {
    player_command_t command; 
    player_status_t player_status;

    buffer_pref_t buffer_pref;
    const char *url;
    
    RingbufHandle_t *buf_handle;    //环形缓存结构
    int ringbuf_size;
    SemaphoreHandle_t ringbuf_sem; /* 互斥信号量句柄 */
    // EventGroupHandle_t ringbuf_eventGroup;

    HTTP_HEAD_VAL *http_head;
    char *http_body;
    int http_body_len;
    esp_http_client_method_t http_method;

    audio_type_t file_type;
    media_stream_t media_stream;
} player_t;

typedef struct {

} radio_controls_t;

typedef struct {
    char *url;
    player_t *player_config;
} web_radio_t;

player_status_t get_player_status();
void init_palyer_handle(player_t *Player);
player_t *get_player_handle();

void audio_player_begin(void);
void audio_player_start();
void audio_player_stop();
void audio_player_pause();
void audio_player_destroy();
void create_decode_task(player_t *player);

#endif /* INCLUDE_AUDIO_PLAYER_H_ */
