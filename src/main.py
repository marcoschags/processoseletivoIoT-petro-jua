from machine import Pin
import time

try:
    from calibration import ESCALA, CAIXA_CHEIA, LIMITE_CRITICO
except ImportError:
    ESCALA = 420
    CAIXA_CHEIA = 5000
    LIMITE_CRITICO = 200

DT_PIN = 4
SCK_PIN = 5


class HX711:
    def __init__(self, dout, pd_sck):
        self.dout = Pin(dout, Pin.IN)
        self.pd_sck = Pin(pd_sck, Pin.OUT)
        self.pd_sck.value(0)

    def read(self):
        if self.dout.value() == 1:
            time.sleep_ms(100)
            if self.dout.value() == 1:
                return 0
        value = 0
        for _ in range(24):
            self.pd_sck.value(1)
            value = (value << 1) | self.dout.value()
            self.pd_sck.value(0)
        self.pd_sck.value(1)
        self.pd_sck.value(0)
        if value & 0x800000:
            value -= 0x1000000
        return value

    def read_grams(self):
        raw = self.read()
        if raw < 0:
            raw = 0
        return int(raw / ESCALA)


sensor = HX711(DT_PIN, SCK_PIN)

print("Sistema Kanban Inicializado")

last_weight = None
last_state = None
last_g_exibido = None
zero_since = 0
ANOMALIA_DEBOUNCE_MS = 14100

STATE_ANOMALIA = "ANOMALIA"
STATE_VAZIA = "VAZIA"
STATE_REGULAR = "REGULAR"

while True:
    weight = sensor.read_grams()

    if last_weight is None or abs(weight - last_weight) >= 5 or weight == 0:
        if last_state != STATE_ANOMALIA and weight != 0:
            print("Leitura: {}g".format(weight))
        if weight == 0:
            if last_weight != 0:
                print("Leitura: {}g".format(weight))
            now = time.ticks_ms()
            if zero_since == 0:
                zero_since = now
            elif time.ticks_diff(now, zero_since) >= ANOMALIA_DEBOUNCE_MS and last_state != STATE_ANOMALIA:
                print("ALERTA: Caixa ausente ou erro de calibração no sensor HX711!")
                last_state = STATE_ANOMALIA
                last_g_exibido = None
        elif weight <= LIMITE_CRITICO:
            zero_since = 0
            if last_state != STATE_VAZIA:
                print("Evento de reposição disparado! Caixa vazia detectada.")
                last_state = STATE_VAZIA
                last_g_exibido = None
        elif weight >= CAIXA_CHEIA and last_state == STATE_VAZIA:
            zero_since = 0
            print("Abastecimento concluído. Caixa cheia.")
            last_state = STATE_REGULAR
        else:
            zero_since = 0
            if last_g_exibido is None or weight != last_g_exibido:
                print("Status: Estoque Regular ({}g)".format(weight))
                last_g_exibido = weight
            last_state = STATE_REGULAR

        last_weight = weight

    time.sleep_ms(2000)
