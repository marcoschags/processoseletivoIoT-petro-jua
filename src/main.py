from machine import Pin
import time

CAIXA_CHEIA = 5000
LIMITE_CRITICO = 200
ESCALA = 420

DT_PIN = 4
SCK_PIN = 5


class HX711:
    def __init__(self, dout, pd_sck):
        self.dout = Pin(dout, Pin.IN)
        self.pd_sck = Pin(pd_sck, Pin.OUT)
        self.pd_sck.value(0)

    def read(self):
        timeout = 200
        while self.dout.value() == 1:
            time.sleep_ms(1)
            timeout -= 1
            if timeout <= 0:
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
last_kg_exibido = None
zero_count = 0

STATE_ANOMALIA = "ANOMALIA"
STATE_VAZIA = "VAZIA"
STATE_REGULAR = "REGULAR"

while True:
    weight = sensor.read_grams()

    if last_weight is None or abs(weight - last_weight) >= 5 or weight == 0:
        if weight == 0:
            zero_count += 1
            if zero_count >= 3 and last_state != STATE_ANOMALIA:
                print("ALERTA: Caixa ausente ou erro de calibração no sensor HX711!")
                last_state = STATE_ANOMALIA
                last_kg_exibido = None
        elif weight <= LIMITE_CRITICO:
            zero_count = 0
            if last_state != STATE_VAZIA:
                print("Evento de reposição disparado! Caixa vazia detectada.")
                last_state = STATE_VAZIA
                last_kg_exibido = None
        elif weight >= CAIXA_CHEIA and last_state == STATE_VAZIA:
            zero_count = 0
            print("Abastecimento concluído. Caixa cheia.")
            last_state = STATE_REGULAR
        else:
            zero_count = 0
            kg_atual = round(weight / 1000.0, 1)
            if last_kg_exibido is None or kg_atual != last_kg_exibido:
                print("Status: Estoque Regular ({:.1f}kg)".format(kg_atual))
                last_kg_exibido = kg_atual
            last_state = STATE_REGULAR

        last_weight = weight

    time.sleep_ms(5000)
