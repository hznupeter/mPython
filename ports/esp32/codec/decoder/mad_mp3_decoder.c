/*
 * mp3_decoder.c
 *
 *  Created on: 13.03.2017
 *      Author: michaelboeckling
 */

#include <stdlib.h>
#include <string.h>

#include "esp_log.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/ringbuf.h"

#include "mad.h"
#include "stream.h"
#include "frame.h"
#include "synth.h"

#include "driver/i2s.h"
#include "audio_renderer.h"
#include "audio_player.h"
#include "mad_mp3_decoder.h"
// #include "common_buffer.h"

#define TAG "mad_decoder"

// The theoretical maximum frame size is 2881 bytes,
// MPEG 2.5 Layer II, 8000 Hz @ 160 kbps, with a padding slot plus 8 byte MAD_BUFFER_GUARD.
#define MAX_FRAME_SIZE (2889)

// The theoretical minimum frame size of 24 plus 8 byte MAD_BUFFER_GUARD.
#define MIN_FRAME_SIZE (32)
#define MAINBUF_SIZE1 2889 //2880 //1940

// static long buf_underrun_cnt;
extern TaskHandle_t http_client_task_handel;

/* default MAD buffer format */
pcm_format_t mad_buffer_fmt = {
    .sample_rate = 44100,
    .bit_depth = I2S_BITS_PER_SAMPLE_16BIT,
    .num_channels = 2,
    .buffer_format = PCM_LEFT_RIGHT
};

typedef struct{
    struct mad_stream *stream;
    struct mad_frame *frame;
    struct mad_synth *synth;
    unsigned char *readBuf;
    int bytesleft;
    unsigned char *readPtr;
    int supply_bytes;
}mp3_decode_t;

static int proccess_tag(mp3_decode_t *decoder)
{
    int tag_len;
    int ringBufRemainBytes = 0;
    size_t len;
    uint8_t *temp = NULL;
    player_t *player = get_player_handle();

    //xSemaphoreTake(player->ringbuf_sem, portMAX_DELAY);
    ringBufRemainBytes = RINGBUF_SIZE - xRingbufferGetCurFreeSize(player->buf_handle); //
    if(ringBufRemainBytes >= 10)
    {
        temp = xRingbufferReceiveUpTo(player->buf_handle,  &len, 500 / portTICK_PERIOD_MS, 10);
        if(temp != NULL)
        {
            ESP_LOGE(TAG, "mp3 TAG? : %x %x %x %x", temp[0], temp[1],temp[2],temp[3]);
            if (memcmp((char *)temp, "ID3", 3) == 0) //mp3? 有标签头，读取所有标签帧并去掉。
            { 
                //获取ID3V2标签头长，以确定MP3数据起始位置
                tag_len = ((temp[6] & 0x7F) << 21) | ((temp[7] & 0x7F) << 14) | ((temp[8] & 0x7F) << 7) | (temp[9] & 0x7F); 
                // ESP_LOGE(TAG, "tag_len: %d %x %x %x %x", tag_len, temp[6], temp[7], temp[8], temp[9]);
                vRingbufferReturnItem(player->buf_handle, (void *)temp);
                do
                {
                    ringBufRemainBytes = RINGBUF_SIZE - xRingbufferGetCurFreeSize(player->buf_handle);
                    if(tag_len <= ringBufRemainBytes) //ring buf中数据多于tag_len，把tag数据读完并退出
                    {
                        temp = xRingbufferReceiveUpTo(player->buf_handle,  &len, 500 / portTICK_PERIOD_MS, tag_len);
                        if(temp != NULL)
                        {
                            vRingbufferReturnItem(player->buf_handle, (void *)temp);
                            return 0;
                        }
                    }
                    else 
                    {
                        temp = xRingbufferReceiveUpTo(player->buf_handle,  &len, 500 / portTICK_PERIOD_MS, ringBufRemainBytes);
                        if(temp != NULL)
                        {
                            vRingbufferReturnItem(player->buf_handle, (void *)temp);
                            tag_len -= len;
                        }
                    }
                } while(tag_len > 0);
            } 
            else //无tag头 把前面读到的10字节加入解码buff
            {
                memcpy(decoder->readBuf, (char *)temp, 10);
                decoder->bytesleft += len;
                decoder->readPtr = decoder->readBuf;
                vRingbufferReturnItem(player->buf_handle, (void *)temp);
                decoder->supply_bytes = MAINBUF_SIZE1 - 10;
            }      
        }
    }  
    return 0;
}

static int read_ringbuf(mp3_decode_t *decoder)
{
    uint32_t ringBufRemainBytes = 0;
    size_t len;
    void *temp = NULL;
    player_t *player = get_player_handle();

    //xSemaphoreTake(player->ringbuf_sem, portMAX_DELAY);
    ringBufRemainBytes = RINGBUF_SIZE - xRingbufferGetCurFreeSize(player->buf_handle); //
    //xSemaphoreGive(player->ringbuf_sem);

    // ESP_LOGE(TAG, "ringBufRemainBytes = %d, supply_bytes = %d", ringBufRemainBytes, Supply_bytes);
    if(ringBufRemainBytes >= decoder->supply_bytes)  //ring buffer remain data enough for decoder need
    { 
        if(decoder->supply_bytes > 0){
            //xSemaphoreTake(player->ringbuf_sem, portMAX_DELAY);
            temp = xRingbufferReceiveUpTo(player->buf_handle,  &len, 500 / portTICK_PERIOD_MS, decoder->supply_bytes);
            //xSemaphoreGive(player->ringbuf_sem);
        }
    }
    else{ 
        if(player->media_stream.eof){ //Stream end
            if(ringBufRemainBytes != 0){
                //xSemaphoreTake(player->ringbuf_sem, portMAX_DELAY);
                temp = xRingbufferReceiveUpTo(player->buf_handle,  &len, 50 / portTICK_PERIOD_MS, ringBufRemainBytes);
                //xSemaphoreGive(player->ringbuf_sem);
            }       
        }  
        else{ 
            renderer_zero_dma_buffer();
            return -1; //ring buffer中数据不够解码器请求，退出等数据补够
        }
    }  

    if ((decoder->bytesleft > 0) && (decoder->readBuf != decoder->readPtr)) //解码缓存中还有数据没处理完，把它移到缓存头部
    {
        memmove(decoder->readBuf, decoder->readPtr, decoder->bytesleft);  //数据移动缓存头部，补充进来的数据接到后面
    }

    if(temp != NULL){
        decoder->readPtr = decoder->readBuf + decoder->bytesleft;
        memcpy(decoder->readPtr, temp, len);
        decoder->bytesleft += len;
        //xSemaphoreTake(player->ringbuf_sem, portMAX_DELAY);
        vRingbufferReturnItem(player->buf_handle, (void *)temp);
        //xSemaphoreGive(player->ringbuf_sem);
    }

    if(ringBufRemainBytes == 0){ //结束的时机选这，保证所有数据可被解码
        return 1;
    }

    // Okay, let MAD decode the buffer.
    mad_stream_buffer(decoder->stream, (unsigned char*) decoder->readBuf, decoder->bytesleft);
    return 0;
}


//Routine to print out an error
static enum mad_flow error(void *data, struct mad_stream *stream, struct mad_frame *frame) {
    ESP_LOGE(TAG, "dec err 0x%04x (%s)", stream->error, mad_stream_errorstr(stream));
    return MAD_FLOW_CONTINUE;
}


//This is the main mp3 decoding task. It will grab data from the input buffer FIFO in the SPI ram and
//output it to the I2S port.
void mad_mp3_decoder_task(void *pvParameters)
{
    player_t *player = pvParameters;
    int status;
    mp3_decode_t *decoder;

    int ret;

    //Allocate structs needed for mp3 decoding
    decoder = calloc(1, sizeof(mp3_decode_t));
    if(decoder == NULL)
        goto abort;
    decoder->stream = malloc(sizeof(struct mad_stream));
    if(decoder->stream == NULL){
        free(decoder);
        ESP_LOGE(TAG, "malloc(stream) failed\n");
        goto abort;
    }
    decoder->frame = malloc(sizeof(struct mad_frame));
    if(decoder->frame == NULL){
        free(decoder->stream);
        free(decoder);
        ESP_LOGE(TAG, "malloc(frame) failed\n");
        goto abort;
    }
    decoder->synth = malloc(sizeof(struct mad_synth));
    if(decoder->synth == NULL){
        free(decoder->stream);
        free(decoder->frame);
        free(decoder);
        ESP_LOGE(TAG, "malloc(synth) failed\n");
        goto abort;
    }
    decoder->readBuf = malloc(MAINBUF_SIZE1);
    if(decoder->readBuf == NULL){
        free(decoder->stream);
        free(decoder->frame);
        free(decoder->synth);
        free(decoder);
        ESP_LOGE(TAG, "read buffer created failed\n");
        goto abort;
    }

    ESP_LOGI(TAG, "decoder start");

    //Initialize mp3 parts
    mad_stream_init(decoder->stream);
    mad_frame_init(decoder->frame);
    mad_synth_init(decoder->synth);

    decoder->supply_bytes = MAINBUF_SIZE1;
    decoder->bytesleft = 0;
    decoder->readPtr = decoder->readBuf;

    proccess_tag(decoder);

    while(1) {
        // calls mad_stream_buffer internally
        status = read_ringbuf(decoder);
        if(status == -1){ //ringbuf remain bytes < decode need bytes
            vTaskDelay(1 / portTICK_PERIOD_MS);
            continue;
        }
        // decode frames until MAD complains
        while(1) 
        {
            // returns 0 or -1
            ret = mad_frame_decode(decoder->frame, decoder->stream);
            if (ret == -1) {
                if (!MAD_RECOVERABLE(decoder->stream->error)) {
                    //We're most likely out of buffer and need to call input() again
                    // next_frame is the position MAD is interested in resuming from 
                    decoder->supply_bytes = decoder->stream->next_frame - decoder->stream->buffer;
                    decoder->readPtr = decoder->readBuf + decoder->supply_bytes;
                    decoder->bytesleft -= decoder->supply_bytes;
                    break;
                }
                error(NULL, decoder->stream, decoder->frame);
                continue;
            }
            mad_synth_frame(decoder->synth, decoder->frame);
        }
        if((player->player_status == STOPPED) || ((player->media_stream.eof) && (status == 1) && (decoder->bytesleft == 0)))
            break;
        else if(player->player_status == PAUSED){
            vTaskSuspend( NULL );
        }
        // ESP_LOGI(TAG, "RAM left %d", esp_get_free_heap_size());
    }

    free(decoder->stream);
    free(decoder->frame);
    free(decoder->synth);
    free(decoder->readBuf);
    free(decoder);

    abort:
    renderer_zero_dma_buffer();
    renderer_stop();
    if(player->file_type == WEB_TYPE)
    {
        if(http_client_task_handel != NULL){
            player->player_status = INITIALIZED;
            vTaskDelete(http_client_task_handel);
            http_client_task_handel = NULL;
            ESP_LOGE(TAG, "play status: %d", player->player_status); 
        }
    }
    else if ( player->file_type == LOCAL_TYPE) {
        player->player_status = INITIALIZED;
    }
    
    // ESP_LOGE(TAG, "helix decoder stack: %d\n", uxTaskGetStackHighWaterMark(NULL));
    ESP_LOGE(TAG, "6. mp3 decode task will delete, RAM left: %d", esp_get_free_heap_size()); 
    vTaskDelete(NULL);
}

/* Called by the NXP modifications of libmad. Sets the needed output sample rate. */
void set_dac_sample_rate(int rate)
{
    mad_buffer_fmt.sample_rate = rate;
}

/* render callback for the libmad synth */
void render_sample_block(short *sample_buff_ch0, short *sample_buff_ch1, int num_samples, unsigned int num_channels)
{
    mad_buffer_fmt.num_channels = num_channels;
    uint32_t len = num_samples * sizeof(short) * num_channels;
    render_samples((char*) sample_buff_ch0, len, &mad_buffer_fmt);
    return;
}

