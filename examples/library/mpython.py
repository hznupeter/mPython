# labplus mPython library
# MIT license; Copyright (c) 2018 labplus
# V1.0 Zhang KaiHua(apple_eat@126.com)

# mpython buildin periphers drivers

# history:
# V1.1 add oled draw function,add buzz.freq().  by tangliufeng
# V1.2 add servo/ui class,by tangliufeng


from machine import I2C, PWM, Pin, ADC, TouchPad,UART
from ssd1106 import SSD1106_I2C
import esp,math,time,network
import ustruct,array
from neopixel import NeoPixel
from esp import dht_readinto
from time import sleep_ms, sleep_us,sleep

pins_remap_esp32 = [33, 32, 35, 34, 39, 0, 16, 17, 26, 25, 
                    36,  2, -1, 18, 19, 21, 5, -1, -1, 22,
                    23,  -1, -1,
                    27, 14, 12, 13, 15, 4]

i2c = I2C(scl=Pin(22), sda=Pin(23), freq=400000)

class Font(object):
    def __init__(self, font_address=0x300000):
        self.font_address = font_address
        buffer = bytearray(18)
        esp.flash_read(self.font_address, buffer)
        self.header, \
            self.height, \
            self.width, \
            self.baseline, \
            self.x_height, \
            self.Y_height, \
            self.first_char,\
            self.last_char = ustruct.unpack('4sHHHHHHH', buffer)
        self.first_char_info_address = self.font_address + 18

    def GetCharacterData(self, c):
        uni = ord(c)
        if uni not in range(self.first_char, self.last_char):
            return None
        char_info_address = self.first_char_info_address + \
            (uni - self.first_char) * 6
        buffer = bytearray(6)
        esp.flash_read(char_info_address, buffer)
        ptr_char_data, len = ustruct.unpack('IH', buffer)   
        if (ptr_char_data) == 0 or (len == 0):
            return None
        buffer = bytearray(len)
        esp.flash_read(ptr_char_data + self.font_address, buffer)
        return buffer


class Accelerometer():
    """  """
    def __init__(self):
        self.addr = 38
        self.i2c = i2c
        self.i2c.writeto(self.addr, b'\x0F\x08')    # set resolution = 10bit
        self.i2c.writeto(self.addr, b'\x11\x00')    # set power mode = normal

    def get_x(self):
        self.i2c.writeto(self.addr, b'\x02', False)
        buf = self.i2c.readfrom(self.addr, 2)
        x = ustruct.unpack('h', buf)[0]
        return x / 4 / 4096

    def get_y(self):
        self.i2c.writeto(self.addr, b'\x04', False)
        buf = self.i2c.readfrom(self.addr, 2)
        y = ustruct.unpack('h', buf)[0]
        return y / 4 / 4096

    def get_z(self):
        self.i2c.writeto(self.addr, b'\x06', False)
        buf = self.i2c.readfrom(self.addr, 2)
        z = ustruct.unpack('h', buf)[0]
        return z / 4 / 4096

class BME280(object):
  def __init__(self):
    self.addr = 119
    # The “ctrl_hum” register sets the humidity data acquisition options of the device
    # 0x01 = [2:0]oversampling ×1
    i2c.writeto(self.addr, b'\xF2\x01') 
    # The “ctrl_meas” register sets the pressure and temperature data acquisition options of the device. 
    # The register needs to be written after changing “ctrl_hum” for the changes to become effective.
    # 0x27 = [7:5]Pressure oversampling ×1 | [4:2]Temperature oversampling ×4 | [1:0]Normal mode
    i2c.writeto(self.addr, b'\xF4\x27')
    # The “config” register sets the rate, filter and interface options of the device. Writes to the “config”
    # register in normal mode may be ignored. In sleep mode writes are not ignored.
    i2c.writeto(self.addr, b'\xF5\x00')
    
    i2c.writeto(self.addr, b'\x88', False)
    bytes = i2c.readfrom(self.addr, 6)
    self.dig_T = ustruct.unpack('Hhh', bytes)
    
    i2c.writeto(self.addr, b'\x8E', False)
    bytes = i2c.readfrom(self.addr, 18)
    self.dig_P = ustruct.unpack('Hhhhhhhhh', bytes)
    
    i2c.writeto(self.addr, b'\xA1', False)
    self.dig_H = array.array('h', [0, 0, 0, 0, 0, 0])
    self.dig_H[0] = i2c.readfrom(self.addr, 1)[0]
    i2c.writeto(self.addr, b'\xE1', False)
    buff = i2c.readfrom(self.addr, 7)
    self.dig_H[1] = ustruct.unpack('h', buff[0:2])[0]
    self.dig_H[2] = buff[2]
    self.dig_H[3] = (buff[3] << 4) | (buff[4] & 0x0F)
    self.dig_H[4] = (buff[5] << 4) | (buff[4] >> 4 & 0x0F)
    self.dig_H[5] = buff[6]
   
  def temperature(self):
    i2c.writeto(self.addr, b'\xFA', False)
    buff = i2c.readfrom(self.addr, 3)
    T = (((buff[0] << 8) | buff[1]) << 4) | (buff[2] >> 4 & 0x0F)
    c1 = (T / 16384.0 - self.dig_T[0] / 1024.0) * self.dig_T[1]
    c2 = ((T / 131072.0 - self.dig_T[0] / 8192.0) * (T / 131072.0 - self.dig_T[0] / 8192.0)) * self.dig_T[2]    
    self.tFine = c1 + c2
    return self.tFine / 5120.0
    
  def pressure(self):
    i2c.writeto(self.addr, b'\xF7', False)
    buff = i2c.readfrom(self.addr, 3)  
    P = (((buff[0] << 8) | buff[1]) << 4) | (buff[2] >> 4 & 0x0F)
    c1 = self.tFine / 2.0 - 64000.0
    c2 = c1 * c1 * self.dig_P[5] / 32768.0
    c2 = c2 + c1 * self.dig_P[4] * 2.0
    c2 = c2 / 4.0 + self.dig_P[3] * 65536.0
    c1 = (self.dig_P[2] * c1 * c1 / 524288.0 + self.dig_P[1] * c1) / 524288.0
    c1 = (1.0 + c1 / 32768.0) * self.dig_P[0]
    if c1 == 0.0:
      return 0;
    p = 1048576.0 - P;
    p = (p - c2 / 4096.0) * 6250.0 / c1
    c1 = self.dig_P[8] * p * p / 2147483648.0
    c2 = p * self.dig_P[7] / 32768.0
    p = p + (c1 + c2 + self.dig_P[6]) / 16.0
    return p
    
  def humidity(self):
    self.temperature()
    
    i2c.writeto(self.addr, b'\xFD', False)
    buff = i2c.readfrom(self.addr, 2)
    H = buff[0] << 8 | buff[1]
    h = self.tFine - 76800.0
    h = (H - (self.dig_H[3] * 64.0 + self.dig_H[4] / 16384.0 * h)) * \
        (self.dig_H[1] / 65536.0 * (1.0 + self.dig_H[5] / 67108864.0 * h * \
        (1.0 + self.dig_H[2] / 67108864.0 * h)))
    h = h * (1.0 - self.dig_H[0] * h / 524288.0)
    if h > 100.0:
      return 100.0
    elif h < 0.0:
      return 0.0
    else:
      return h


class TextMode():
    normal = 1
    rev = 2
    trans = 3
    xor = 4


class OLED(SSD1106_I2C):
    """ 128x64 oled display """
    def __init__(self):
        super().__init__(128, 64, i2c)
        self.f = Font()
        if self.f is None:
            raise Exception('font load failed')

    def DispChar(self, s, x, y, mode=TextMode.normal):
        if self.f is None:
            return
        for c in s:
            data = self.f.GetCharacterData(c)
            if data is None:
                x = x + self.width
                continue
            width, bytes_per_line = ustruct.unpack('HH', data[:4])
            # print('character [%d]: width = %d, bytes_per_line = %d' % (ord(c)
            # , width, bytes_per_line))
            for h in range(0, self.f.height):
                w = 0
                i = 0
                while w < width:
                    mask = data[4 + h * bytes_per_line + i]
                    if (width - w) >= 8:
                        n = 8
                    else:
                        n = width - w
                    py = y + h
                    page = py >> 3
                    bit = 0x80 >> (py % 8)
                    for p in range(0, n):
                        px = x + w + p
                        c = 0
                        if (mask & 0x80) != 0:
                            if mode == TextMode.normal or \
                               mode == TextMode.trans:
                                c = 1
                            if mode == TextMode.rev:
                                c = 0
                            if mode == TextMode.xor:                               
                                c = self.buffer[page * 128 + px] & bit
                                if c != 0:
                                    c = 0
                                else:
                                    c = 1
                                print("px = %d, py = %d, c = %d" % (px, py, c))
                            super().pixel(px, py, c)
                        else:
                            if mode == TextMode.normal:
                                c = 0
                                super().pixel(px, py, c)
                            if mode == TextMode.rev:
                                c = 1
                                super().pixel(px, py, c)
                        mask = mask << 1
                    w = w + 8
                    i = i + 1
            x = x + width + 1

    def circle(self, x0, y0, radius , c):
            # Circle drawing function.  Will draw a single pixel wide circle with
            # center at x0, y0 and the specified radius.
            f = 1 - radius
            ddF_x = 1
            ddF_y = -2 * radius
            x = 0
            y = radius
            super().pixel(x0, y0 + radius, c)
            super().pixel(x0, y0 - radius, c)
            super().pixel(x0 + radius, y0, c)
            super().pixel(x0 - radius, y0, c)
            while x < y:
                if f >= 0:
                    y -= 1
                    ddF_y += 2
                    f += ddF_y
                x += 1
                ddF_x += 2
                f += ddF_x
                super().pixel(x0 + x, y0 + y, c)
                super().pixel(x0 - x, y0 + y, c)
                super().pixel(x0 + x, y0 - y, c)
                super().pixel(x0 - x, y0 - y, c)
                super().pixel(x0 + y, y0 + x, c)
                super().pixel(x0 - y, y0 + x, c)
                super().pixel(x0 + y, y0 - x, c)
                super().pixel(x0 - y, y0 - x, c)


    def fill_circle(self, x0, y0, radius, c):
        # Filled circle drawing function.  Will draw a filled circule with
        # center at x0, y0 and the specified radius.
        super().vline(x0, y0 - radius, 2*radius + 1, c)
        f = 1 - radius
        ddF_x = 1
        ddF_y = -2 * radius
        x = 0
        y = radius
        while x < y:
            if f >= 0:
                y -= 1
                ddF_y += 2
                f += ddF_y
            x += 1
            ddF_x += 2
            f += ddF_x
            super().vline(x0 + x, y0 - y, 2*y + 1, c)
            super().vline(x0 + y, y0 - x, 2*x + 1, c)
            super().vline(x0 - x, y0 - y, 2*y + 1, c)
            super().vline(x0 - y, y0 - x, 2*x + 1, c)
            

    def triangle(self, x0, y0, x1, y1, x2, y2, c):
            # Triangle drawing function.  Will draw a single pixel wide triangle
            # around the points (x0, y0), (x1, y1), and (x2, y2).
            super().line(x0, y0, x1, y1, c)
            super().line(x1, y1, x2, y2, c)
            super().line(x2, y2, x0, y0, c)


    def fill_triangle(self, x0, y0, x1, y1, x2, y2, c):
        # Filled triangle drawing function.  Will draw a filled triangle around
        # the points (x0, y0), (x1, y1), and (x2, y2).
        if y0 > y1:
            y0, y1 = y1, y0
            x0, x1 = x1, x0
        if y1 > y2:
            y2, y1 = y1, y2
            x2, x1 = x1, x2
        if y0 > y1:
            y0, y1 = y1, y0
            x0, x1 = x1, x0
        a = 0
        b = 0
        y = 0
        last = 0
        if y0 == y2:
            a = x0
            b = x0
            if x1 < a:
                a = x1
            elif x1 > b:
                b = x1
            if x2 < a:
                a = x2
            elif x2 > b:
                b = x2
            super().hline(a, y0, b-a+1, c)
            return
        dx01 = x1 - x0
        dy01 = y1 - y0
        dx02 = x2 - x0
        dy02 = y2 - y0
        dx12 = x2 - x1
        dy12 = y2 - y1
        if dy01 == 0:
            dy01 = 1
        if dy02 == 0:
            dy02 = 1
        if dy12 == 0:
            dy12 = 1
        sa = 0
        sb = 0
        if y1 == y2:
            last = y1
        else:
            last = y1-1
        for y in range(y0, last+1):
            a = x0 + sa // dy01
            b = x0 + sb // dy02
            sa += dx01
            sb += dx02
            if a > b:
                a, b = b, a
            super().hline(a, y, b-a+1, c)
        sa = dx12 * (y - y1)
        sb = dx02 * (y - y0)
        while y <= y2:
            a = x1 + sa // dy12
            b = x0 + sb // dy02
            sa += dx12
            sb += dx02
            if a > b:
                a, b = b, a
            super().hline(a, y, b-a+1, c)
            y += 1
            

    def Bitmap(self, x, y, bitmap, w, h,c):
        byteWidth = int((w + 7) / 8)
        for j in range(h):
            for i in range(w):
                if bitmap[int(j * byteWidth + i / 8)] & (128 >> (i & 7)):
                    super().pixel(x+i, y+j, c)


    def drawCircleHelper(self, x0, y0, r, cornername, c):
            f = 1 - r
            ddF_x = 1
            ddF_y = -2 * r 
            x = 0
            y = r
            
            tf = f
            while x < y:
            
                if (f >= 0):
                    # y--   y -= 1 below
                    y -= 1
                    ddF_y += 2
                    f += ddF_y      
            #   x++ 
                ddF_x += 2
                f += ddF_x
                
                if (cornername & 0x4):
                    super().pixel(x0 + x, y0 + y, c)
                    super().pixel(x0 + y, y0 + x, c)
                
                if (cornername & 0x2):
                    super().pixel(x0 + x, y0 - y, c)
                    super().pixel(x0 + y, y0 - x, c)
            
                if (cornername & 0x8):
                    super().pixel(x0 - y, y0 + x, c)
                    super().pixel(x0 - x, y0 + y, c)
                
                if (cornername & 0x1):
                    super().pixel(x0 - y, y0 - x, c)
                    super().pixel(x0 - x, y0 - y, c)
                x += 1

    
    def RoundRect( self, x, y, w, h, r, c):
        self.hline(x + r , y , w - 2 * r , c)
        self.hline(x + r , y + h - 1, w - 2 * r , c)
        self.vline(x, y + r, h - 2 * r , c)
        self.vline(x + w - 1, y + r , h - 2 * r , c)
        
        self.drawCircleHelper(x + r  , y + r , r , 1, c)
        self.drawCircleHelper(x + w - r - 1, y + r  , r , 2, c)
        self.drawCircleHelper(x + w - r - 1, y + h - r - 1, r , 4, c)
        self.drawCircleHelper(x + r  , y + h - r - 1, r , 8, c)


class Buzz(object):   
    def __init__(self, pin=6):
        self.id = pins_remap_esp32[pin]
        self.io = Pin(self.id) 
        self.io.value(1)
        self.isOn = False

    def on(self, freq=500):
        if self.isOn is False:
            self.pwm = PWM(self.io, freq, 512)
            self.isOn = True

    def off(self):
        if self.isOn:
            self.pwm.deinit()
            self.io.init(self.id, Pin.OUT)
            self.io.value(1)
            self.isOn = False

    def freq(self, freq):
        self.pwm.freq(freq)


class PinMode(object):
    IN = 1
    OUT = 2
    PWM = 3
    ANALOG = 4


class MPythonPin():
    def __init__(self, pin, mode=PinMode.IN,pull=None):
        if mode not in [PinMode.IN, PinMode.OUT, PinMode.PWM, PinMode.ANALOG]:
            raise TypeError("mode must be 'IN, OUT, PWM, ANALOG'")
        if pin == 4:
            raise TypeError("P4 is used for light sensor")
        if pin == 10:
            raise TypeError("P10 is used for sound sensor")
        try:
            self.id = pins_remap_esp32[pin]
        except IndexError:
            raise IndexError("Out of Pin range")
        if mode == PinMode.IN:
            if pin in [3]:
                raise TypeError('IN not supported on P%d' %pin)
            self.Pin=Pin(self.id, Pin.IN, pull)
        if mode == PinMode.OUT:
            if pin in [2,3]:
                raise TypeError('OUT not supported on P%d' %pin)
            self.Pin=Pin(self.id, Pin.OUT,pull)
        if mode == PinMode.PWM:
            if pin not in [0,1,5,6,7,8,9,11,13,14,15,16,19,20,23,24,25,26,27,28]:
                raise TypeError('PWM not supported on P%d' %pin)
            self.pwm = PWM(Pin(self.id), duty=0)
        if mode == PinMode.ANALOG:
            if pin not in [0, 1, 2, 3, 4, 10]:
                raise TypeError('ANALOG not supported on P%d' %pin)
            self.adc= ADC(Pin(self.id))
            self.adc.atten(ADC.ATTN_11DB)
        self.mode = mode

    def irq(self,handler=None, trigger=Pin.IRQ_RISING):
        if not self.mode == PinMode.IN:
            raise TypeError('the pin is not in IN mode')
        return self.Pin.irq(handler,trigger)

    def read_digital(self):
        if not self.mode == PinMode.IN:
            raise TypeError('the pin is not in IN mode')
        return self.Pin.value()

    def write_digital(self, value):
        if not self.mode == PinMode.OUT:
            raise TypeError('the pin is not in OUT mode')
        self.Pin.value(value)

    def read_analog(self):
        if not self.mode == PinMode.ANALOG:
            raise TypeError('the pin is not in ANALOG mode')
        return self.adc.read()

    def write_analog(self, duty, freq=1000):
        if not self.mode == PinMode.PWM:
            raise TypeError('the pin is not in PWM mode')        
        self.pwm.freq(freq)
        self.pwm.duty(duty)


'''
# to be test
class LightSensor(ADC):
    
    def __init__(self):
        super().__init__(Pin(pins_remap_esp32[4]))
        # super().atten(ADC.ATTN_11DB)
    
    def value(self):
        # lux * k * Rc = N * 3.9/ 4096
        # k = 0.0011mA/Lux
        # lux = N * 3.9/ 4096 / Rc / k
        return super().read() * 1.1 / 4095 / 6.81 / 0.011
    
'''

def numberMap(inputNum,bMin,bMax,cMin,cMax):
    outputNum = 0
    outputNum =((cMax - cMin) / (bMax - bMin))*(inputNum - bMin)+cMin
    return outputNum

class Servo:
    def __init__(self, pin, min_us=750, max_us=2250, actuation_range=180):
        self.min_us = min_us
        self.max_us = max_us
        self.actuation_range = actuation_range
        self.servoPin=MPythonPin(pin,PinMode.PWM)
        

    def write_us(self, us):
        if us < self.min_us or us > self.max_us:
            raise ValueError("us out of range")
        duty = round(us / 20000 * 1023)
        self.servoPin.write_analog(duty, 50)

    def write_angle(self, angle):
        if angle < 0 or angle > self.actuation_range:
            raise ValueError("Angle out of range")
        us_range = self.max_us - self.min_us
        us = self.min_us + round(angle * us_range / self.actuation_range)
        self.write_us(us)


class UI():

    def ProgressBar(self, x, y, width, height, progress):

        radius = int(height / 2)
        xRadius = x + radius
        yRadius = y + radius
        doubleRadius = 2 * radius
        innerRadius = radius - 2

        oled.RoundRect(x,y,width,height,radius,1)
        maxProgressWidth = int((width - doubleRadius + 1) * progress / 100)
        oled.fill_circle(xRadius, yRadius, innerRadius,1)
        oled.fill_rect(xRadius + 1, y + 2, maxProgressWidth, height - 3,1)
        oled.fill_circle(xRadius + maxProgressWidth, yRadius, innerRadius,1)

    def stripBar(self, x, y, width, height, progress,dir=1,frame=1):

        oled.rect(x,y,width,height,frame)
        if  dir:
            Progress=int(progress/100 *width)
            oled.fill_rect(x,y,Progress,height,1)
        else:
            Progress=int(progress/100 *height)
            oled.fill_rect(x,y+(height-Progress),width,Progress,1)

    class multiScreen:

        def __init__(self,framelist,w,h):
            self.framelist=framelist
            self.width=w
            self.hight=h
            self.frameCount=len(framelist)
            self.activeSymbol =bytearray([0x00, 0x18, 0x3c, 0x7e, 0x7e, 0x3c, 0x18, 0x00])
            self.inactiveSymbol =bytearray([0x00, 0x0, 0x0, 0x18, 0x18, 0x0, 0x0, 0x00])
            self.SymbolInterval=1
            

        def drawScreen(self,index):
            self.index=index
            oled.fill(0)
            oled.Bitmap(int(64-self.width/2),int(0.3*self.hight),self.framelist[self.index], self.width,self.hight,1)
            SymbolWidth=self.frameCount*8+(self.frameCount-1)*self.SymbolInterval
            SymbolCenter=int(SymbolWidth/2)
            starX=64-SymbolCenter
            for i in range(self.frameCount):
                x=starX+i*8+i*self.SymbolInterval
                y=int(1.1*self.hight)+8
                if i==self.index:
                    oled.Bitmap(x,y,self.activeSymbol,8,8,1)
                else:
                    oled.Bitmap(x,y,self.inactiveSymbol,8,8,1)
    
        def nextScreen(self):
            self.index=(self.index+1)%self.frameCount
            self.drawScreen(self.index)

    class Clock:

        def __init__(self,x,y,radius):          #定义时钟中心点和半径
            self.xc=x
            self.yc=y
            self.r=radius

        def settime(self):          #设定时间
            t = time.localtime()
            self.hour=t[3]
            self.min=t[4]
            self.sec=t[5]

        def drawDial(self):                    #画钟表刻度
            r_tic1=self.r-1
            r_tic2=self.r-2

            oled.circle(self.xc, self.yc, self.r, 1)
            oled.fill_circle(self.xc, self.yc, 2, 1)

            for h in range(12):
                at = math.pi * 2.0 * h / 12.0
                x1 =round(self.xc + r_tic1 * math.sin(at))
                x2 = round(self.xc + r_tic2 * math.sin(at))
                y1 = round(self.yc - r_tic1 * math.cos(at))
                y2 = round(self.yc - r_tic2 * math.cos(at))
                oled.line(x1,y1,x2,y2,1)

        def drawHour(self):                      #画时针

            r_hour=int(self.r/10.0*5)
            ah=math.pi*2.0*(( self.hour%12)+self.min/60.0)/12.0
            xh=int(self.xc + r_hour * math.sin(ah))
            yh = int(self.yc - r_hour * math.cos(ah))
            oled.line(self.xc, self.yc, xh, yh, 1)

        def drawMin(self):                       #画分针

            r_min=int(self.r/10.0*7)
            am=math.pi*2.0*self.min/60.0

            xm = round(self.xc + r_min * math.sin(am))
            ym = round(self.yc - r_min * math.cos(am))
            oled.line(self.xc,self.yc, xm, ym, 1)

        def drawSec(self):                        #画秒针
            
            r_sec=int(self.r/10.0*9)
            asec = math.pi * 2.0 * self.sec / 60.0
            xs = round(self.xc + r_sec * math.sin(asec))
            ys = round(self.yc - r_sec * math.cos(asec))
            oled.line(self.xc, self.yc, xs, ys, 1)
        
        def drawClock(self):                      #画完整钟表
            
            self.drawDial()
            self.drawHour()
            self.drawMin()
            self.drawSec()

        def clear(self):                           #清除

            oled.fill_circle(self.xc, self.yc, self.r, 0)

class wifi:

    def __init__(self):
        self.sta=network.WLAN(network.STA_IF)
        self.ap=network.WLAN(network.AP_IF)


    def connectWiFi(self,ssid,passwd):
        self.sta.active(True)
        self.sta.connect(ssid,passwd)
        while(self.sta.ifconfig()[0]=='0.0.0.0'):
            sleep_ms(200)
            print('Connecting to network...')
        print('WiFi Connection Successful,Network Config:%s' %str(self.sta.ifconfig()))

    def disconnectWiFi(self):
        self.sta.disconnect()
        self.sta.active(False)
        print('disconnect WiFi...')

    def enable_APWiFi(self,essid,channel):
        self.ap.active(True)
        self.ap.config(essid=essid,channel=channel)

    def disable_APWiFi(self):
        self.ap.active(False)
        print('disable AP WiFi...')

class DHTBase:
    def __init__(self, pin):
        self.id = pins_remap_esp32[pin]
        self.io = Pin(self.id) 
        self.buf = bytearray(5)

    def measure(self):
        buf = self.buf
        dht_readinto(self.io, buf)
        if (buf[0] + buf[1] + buf[2] + buf[3]) & 0xff != buf[4]:
            raise Exception("checksum error")

class DHT11(DHTBase):
    def humidity(self):
        return self.buf[0]

    def temperature(self):
        return self.buf[2]

class DHT22(DHTBase):
    def humidity(self):
        return (self.buf[0] << 8 | self.buf[1]) * 0.1

    def temperature(self):
        t = ((self.buf[2] & 0x7f) << 8 | self.buf[3]) * 0.1
        if self.buf[2] & 0x80:
            t = -t
        return t

# buzz
buzz = Buzz()

# display
oled = OLED()
display = oled

# 3 axis accelerometer
accelerometer = Accelerometer()

# bm280
try:
    bme280=BME280()
except:
    pass

# 3 rgb leds
rgb = NeoPixel(Pin(17, Pin.OUT), 3, 3, 1)
rgb.write()

# light sensor
light = ADC(Pin(39))

# sound sensor
sound = ADC(Pin(36))


# buttons
button_a = Pin(0, Pin.IN, Pin.PULL_UP)
button_b = Pin(2, Pin.IN, Pin.PULL_UP)

# touchpad
touchPad_P = TouchPad(Pin(27))
touchPad_Y = TouchPad(Pin(14))
touchPad_T = TouchPad(Pin(12))
touchPad_H = TouchPad(Pin(13))
touchPad_O = TouchPad(Pin(15))
touchPad_N = TouchPad(Pin(4))
