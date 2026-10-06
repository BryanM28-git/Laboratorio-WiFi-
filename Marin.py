import network
import socket
import time
from machine import Pin, ADC
import dht
import json

# ================= CONFIGURACIÓN =================
WIFI_SSID = "TU_RED_WIFI"        # Pon aquí el nombre de tu Wi-Fi
WIFI_PASS = "TU_CONTRASEÑA"      # Pon aquí la clave de tu Wi-Fi
APP_IP = "10.0.220.211"          # IP de tu celular con MIT App Inventor
UDP_PORT = 1234                  # Puerto UDP para la comunicación

# ================= PINES =================
dht_sensor = dht.DHT11(Pin(4))

ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)  # Atenuación 11 dB: permite leer hasta ~3.3 V (escala 0-4095)

actuadores = [
    Pin(12, Pin.OUT), # Actuador 0 (led_amarillo)
    Pin(13, Pin.OUT), # Actuador 1 (led_rojo)
    Pin(14, Pin.OUT), # Actuador 2 (led_blanco)
    Pin(27, Pin.OUT)  # Actuador 3 (led_azul)
]

# ================= FUNCIONES =================
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Conectando a Wi-Fi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            pass
    print("Conectado! IP del ESP32:", wlan.ifconfig()[0])

# ================= INICIO DEL SISTEMA =================
conectar_wifi()

# Configuración del Socket UDP como Servidor y Cliente
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', UDP_PORT))
# Timeout pequeño (50ms) para no pausar el bucle mientras espera comandos
sock.settimeout(0.05)

ultima_lectura_dht = 0
temp = 0
hum = 0

print("Iniciando transmisión UDP a 4 Hz...")

while True:
    tiempo_actual = time.ticks_ms()

    # 1. Lectura de Sensores
    # El DHT11 se lee cada 2 segundos, pero el ciclo sigue corriendo a 4 Hz
    if time.ticks_diff(tiempo_actual, ultima_lectura_dht) > 2000:
        try:
            dht_sensor.measure()
            temp = dht_sensor.temperature()
            hum = dht_sensor.humidity()
            ultima_lectura_dht = tiempo_actual
        except OSError:
            print("Esperando estabilización del DHT11...")

    # El LDR se lee rapidísimo en cada ciclo
    luminosidad = ldr.read()

    # 2. Empaquetado y envío de datos (Las llaves deben ir en minúsculas)
    datos_envio = {
        "temperatura": temp,
        "humedad": hum,
        "luminosidad": luminosidad
    }
    mensaje_salida = json.dumps(datos_envio)
    sock.sendto(mensaje_salida.encode(), (APP_IP, UDP_PORT))

    # 3. Recepción de comandos desde los interruptores de la App
    try:
        data, addr = sock.recvfrom(1024)
        comando = json.loads(data.decode())

        # Espera JSON tipo: {"actuador": 0, "estado": 1}
        idx = comando.get("actuador")
        estado = comando.get("estado")

        if idx is not None and estado is not None and 0 <= idx < 4:
            actuadores[idx].value(estado)
            print(f"Actuador {idx} cambiado a {estado}")

    except OSError:
        pass # No llegaron datos en este ciclo (es normal)
    except Exception as e:
        print("Error al procesar comando:", e)

    # 4. Control de velocidad a 4 Hz (4 veces por segundo)
    # 200 ms de sleep + 50 ms de timeout del socket = 250 ms por ciclo
    time.sleep(0.2)
  
