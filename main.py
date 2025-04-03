#! /usr/bin/env python3
from ctypes.util import find_library
import numpy as np
import ctypes as ct
import cv2
import os
import datetime
import time

#Define EvoIRFrameMetadata structure for additional frame infos
class EvoIRFrameMetadata(ct.Structure):
     _fields_ = [("counter", ct.c_uint),
                 ("counterHW", ct.c_uint),
                 ("timestamp", ct.c_longlong),
                 ("timestampMedia", ct.c_longlong),
                 ("flagState", ct.c_int),
                 ("tempChip", ct.c_float),
                 ("tempFlag", ct.c_float),
                 ("tempBox", ct.c_float),
                 ]

# load library
if os.name == 'nt':
        #windows:
        libir = ct.CDLL('.\\libirimager.dll') 
        pathFormat = b'.'
        pathLog = b'.\\logs\\win11'
        pathXml = b'.\\generic_Win.xml'
else:
        #linux:
        libir = ct.cdll.LoadLibrary(ct.util.find_library("irdirectsdk"))
        pathFormat = b''
        pathLog = b'./logs/rasp'
        pathXml = b'./generic_Lin.xml'

# init vars
palette_width, palette_height = ct.c_int(), ct.c_int()
thermal_width, thermal_height = ct.c_int(), ct.c_int()
serial = ct.c_ulong()
focus_position = ct.c_float()
pallete = ct.c_int()

# tecla para sair do programa
key = 'p'

# Definir opções de paleta da câmera
PALETTE_OPTIONS = {
        1: "AlarmBlue",
        2: "AlarmBlueHi",
        3: "GrayBW",
        4: "GrayWB",
        5: "AlarmGreen",
        6: "Iron",
        7: "IronHi",
        8: "Medical",
        9: "Rainbow",
        10: "RainbowHi",
        11: "AlarmRed",
}

# Mapeamento das paletas da câmera para as paletas do OpenCV
OPENCV_PALETTES = {
        1: cv2.COLORMAP_COOL,
        2: cv2.COLORMAP_WINTER,
        3: cv2.COLORMAP_BONE,
        4: cv2.COLORMAP_BONE,
        5: cv2.COLORMAP_SPRING,
        6: cv2.COLORMAP_JET,
        7: cv2.COLORMAP_TURBO,
        8: cv2.COLORMAP_HOT,
        9: cv2.COLORMAP_RAINBOW,
        10: cv2.COLORMAP_PARULA,
        11: cv2.COLORMAP_AUTUMN,
}

def criar_barra_escala(temp_min, temp_max, colormap, height):
    """
    Creates a temperature scale bar with a white border next to the thermal image.
    The top represents the maximum temperature, and the bottom represents the minimum.
    """
    scale_width = 50  # Scale bar width
    border_thickness = 5  # White border thickness

    # Create vertical gradient for temperature scale
    scale_bar = np.linspace(temp_max, temp_min, height).reshape(height, 1)
    scale_bar = ((scale_bar - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
    scale_bar_colored = cv2.applyColorMap(scale_bar, colormap)

    # Ensure the scale bar matches the thermal image height
    scale_bar_colored = cv2.resize(scale_bar_colored, (scale_width, height))

    # Add a white border around the scale bar
    scale_bar_with_border = cv2.copyMakeBorder(
        scale_bar_colored,
        border_thickness, border_thickness,  # Top and bottom border
        border_thickness, border_thickness,  # Left and right border
        cv2.BORDER_CONSTANT, value=(255, 255, 255)  # White color
    )

    # **Re-add temperature labels at the top and bottom**
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_thickness = 1
    text_color = (0, 0, 0)  # Black text for better contrast

    # **Top label (max temperature)**
    cv2.putText(scale_bar_with_border, f"{temp_max:.1f}C",
                (5, border_thickness + 15),  # Position inside the top border
                font, font_scale, text_color, font_thickness, cv2.LINE_AA)

    # **Bottom label (min temperature)**
    cv2.putText(scale_bar_with_border, f"{temp_min:.1f}C",
                (5, height + border_thickness - 5),  # Position inside the bottom border
                font, font_scale, text_color, font_thickness, cv2.LINE_AA)

    return scale_bar_with_border

# init EvoIRFrameMetadata structure
metadata = EvoIRFrameMetadata()

# init lib
ret = libir.evo_irimager_usb_init(pathXml, pathFormat, pathLog) 

########################################################################
# get the serial number
try:
        ret = libir.evo_irimager_get_serial(ct.byref(serial))

        if ret == 0:
                print ("============================")
                print(f"Serial da câmera: {serial.value}")
                print ("============================")
        elif ret == -1:
                print ("============================")
                print("Erro ao ler serial da câmera")
                print ("============================")

except Exception as e:
        print ("============================")
        print(f"Erro inesperado ao ler o serial: {e}")
        print ("============================")

########################################################################


########################################################################
# for the focus motor
focus = 80 # 0% - 100%
try:
        ret = libir.evo_irimager_set_focusmotor_pos(ct.c_float(focus)) #deve ser um float do python

        if ret == 0:
                print(f"Posição do motor de foco ajustado para: {focus}%")
                time.sleep(4) # tempo para o motor alcançar o limite definido - considerado pior caso: step de 0% para 100%
                ret = libir.evo_irimager_get_focusmotor_pos(ct.byref(focus_position))
                if ret == 0:
                        print(f"Valor de leitura da posição do motor de foco: {focus_position.value}%")
                        print ("============================")
                elif ret == -1:
                        print("Erro ao definir a posição do motor de foco")
                        print ("============================")
                elif ret < 0:
                        print("Ajuste de posição do motor do foco não disponível para esse modelo")
                        print ("============================")
        elif ret == -1:
                print("Erro ao definir a posição do motor de foco")
                print ("============================")

except Exception as e:
        print(f"Ocorreu um erro desconhecido ao definir a posição do motor do foco: {e}")
        print ("============================")

########################################################################
# set thermic pallet options
id = 11
if id not in PALETTE_OPTIONS:
        # Formatar a lista de opções disponíveis
        options_list = "\n".join([f"{k}: {v}" for k, v in PALETTE_OPTIONS.items()])
        print(f"Erro: ID de paleta inválido. Escolha uma das opções abaixo:\n{options_list}")
        exit()  # Encerra o programa

try:
        pallete = PALETTE_OPTIONS[id]
        ret = libir.evo_irimager_set_palette(pallete)
        if ret == 0:
                print(f"Paleta definida para '{pallete} ' (ID {id}).")
                print ("============================")

        elif ret == -1:
                print ("============================")
                print("Erro ao definir a paleta de cores")
                print ("============================")

except Exception as e:
        print(f"Ocorreu um erro desconhecido ao definir a paleta da imagem térmica: {e}")
        print ("============================")     

########################################################################


# get thermal image size
libir.evo_irimager_get_thermal_image_size(ct.byref(thermal_width), ct.byref(thermal_height))
print('thermal width: ' + str(thermal_width.value))
print('thermal height: ' + str(thermal_height.value))

# init thermal data container
np_thermal = np.zeros([thermal_width.value * thermal_height.value], dtype=np.uint16)
npThermalPointer = np_thermal.ctypes.data_as(ct.POINTER(ct.c_ushort))

# get palette image size, width is different to thermal image width due to stride alignment!!!
libir.evo_irimager_get_palette_image_size(ct.byref(palette_width), ct.byref(palette_height))
print('palette width: ' + str(palette_width.value))
print('palette height: ' + str(palette_height.value))

# init image container
np_img = np.zeros([palette_width.value * palette_height.value * 3], dtype=np.uint8)
npImagePointer = np_img.ctypes.data_as(ct.POINTER(ct.c_ubyte))

# get timestamp for the image. metadata.timestamp() will show faulty values under windows
# as it uses directShow() which is now outdated. Still works fine with Linux based OS.
# Alternative, CounterHW can be used to get the HW Counter from the camera directly.
# (n)HZ = 1Sec -> (n) CounterHW = 1Sec
time_stamp = datetime.datetime.now().strftime("%H:%M:%S %d %B %Y")
show_time_stamp = False



# capture and display image till q is pressed
while chr(cv2.waitKey(1) & 255) != key:

        if show_time_stamp:
               print(time_stamp)

        #get thermal and palette image with metadat
        ret = libir.evo_irimager_get_thermal_palette_image_metadata(
              thermal_width, 
              thermal_height, 
              npThermalPointer, 
              palette_width, 
              palette_height, 
              npImagePointer, 
              ct.byref(metadata))

        if ret != 0:
                print('error on evo_irimager_get_thermal_palette_image ' + str(ret))
                continue

        # Conversão para °C -  vide função 'evo_irimager_get_thermal_image' no arquivo 'direct_binding.h'
        temperatures = (np_thermal.reshape(thermal_height.value, thermal_width.value) - 1000.0) / 10.0 

        # Calculate maximum and minimum temperature
        temp_max = 40
        print('max temp',temp_max)
        temp_min = 20
        print('min temp',temp_min)
        print('mean temp: ' + str(temperatures.mean()))

        temperatures = np.clip(temperatures, temp_min, temp_max)

        if temp_max != temp_min:
                # Normalizar os valores para 8 bits (0-255)
                normalized_img = ((temperatures - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
        else:
                # Se temperatura mínima e máxima forem iguais, criar imagem preta
                normalized_img = np.zeros_like(temperatures, dtype=np.uint8)
                print("Aviso: Temperatura máxima e mínima são iguais, imagem pode estar comprometida.")

        # Aplicar a mesma paleta definida na câmera
        colormap = OPENCV_PALETTES.get(id, cv2.COLORMAP_JET)
        colored_img = cv2.applyColorMap(normalized_img, colormap)

        # Create scale bar with a white border
        scale_bar = criar_barra_escala(temp_min, temp_max, colormap, colored_img.shape[0])

        # **Resize scale bar to match the height of the thermal image**
        scale_bar_resized = cv2.resize(scale_bar, (scale_bar.shape[1], colored_img.shape[0]))

        # **Combine the thermal image with the scale bar**
        final_img = np.hstack((colored_img, scale_bar_resized))

        # **Display the final thermal image with the scale bar**
        cv2.imshow("Thermal Image with Scale", final_img)

# **Salvar corretamente a imagem com a barra de escala**
cv2.imwrite("thermal_image_with_scale.png", final_img)
print(f"📸 Imagem térmica salva com a barra de escala!")

libir.evo_irimager_terminate()
