import numpy as np
import ctypes as ct
import cv2
import os
import time

class EvoIRCamera:
    class EvoIRFrameMetadata(ct.Structure):
        _fields_ = [("counter", ct.c_uint),
                    ("counterHW", ct.c_uint),
                    ("timestamp", ct.c_longlong),
                    ("timestampMedia", ct.c_longlong),
                    ("flagState", ct.c_int),
                    ("tempChip", ct.c_float),
                    ("tempFlag", ct.c_float),
                    ("tempBox", ct.c_float)]

    PALETTE_OPTIONS = {
        1: "AlarmBlue", 2: "AlarmBlueHi", 3: "GrayBW", 4: "GrayWB", 5: "AlarmGreen",
        6: "Iron", 7: "IronHi", 8: "Medical", 9: "Rainbow", 10: "RainbowHi", 11: "AlarmRed"
    }

    OPENCV_PALETTES = {
        1: cv2.COLORMAP_COOL, 2: cv2.COLORMAP_WINTER, 3: cv2.COLORMAP_BONE, 4: cv2.COLORMAP_BONE,
        5: cv2.COLORMAP_SPRING, 6: cv2.COLORMAP_JET, 7: cv2.COLORMAP_TURBO, 8: cv2.COLORMAP_HOT,
        9: cv2.COLORMAP_RAINBOW, 10: cv2.COLORMAP_PARULA, 11: cv2.COLORMAP_AUTUMN
    }

    def __init__(self, palette_id=11):
        self.key_exit = 'q'
        self.palette_id = palette_id
        self.metadata = self.EvoIRFrameMetadata()

        if os.name == 'nt':
            self.libir = ct.CDLL('.\\libirimager.dll')
            path_format = b'.'
            path_log = b'.\\logs\\win11'
            path_xml = b'.\\generic_Win.xml'
        else:
            self.libir = ct.cdll.LoadLibrary(ct.util.find_library("irdirectsdk"))
            path_format = b''
            path_log = b'./logs/rasp'
            path_xml = b'./generic_Lin.xml'

        ret = self.libir.evo_irimager_usb_init(path_xml, path_format, path_log)
        if ret != 0:
            raise RuntimeError("Erro ao inicializar a câmera.")

        self.serial = ct.c_ulong()
        self.thermal_width = ct.c_int()
        self.thermal_height = ct.c_int()
        self.palette_width = ct.c_int()
        self.palette_height = ct.c_int()

        self.libir.evo_irimager_get_serial(ct.byref(self.serial))
        self.libir.evo_irimager_get_thermal_image_size(ct.byref(self.thermal_width), ct.byref(self.thermal_height))
        self.libir.evo_irimager_get_palette_image_size(ct.byref(self.palette_width), ct.byref(self.palette_height))

        self.np_thermal = np.zeros([self.thermal_width.value * self.thermal_height.value], dtype=np.uint16)
        self.npThermalPointer = self.np_thermal.ctypes.data_as(ct.POINTER(ct.c_ushort))
        self.np_img = np.zeros([self.palette_width.value * self.palette_height.value * 3], dtype=np.uint8)
        self.npImagePointer = self.np_img.ctypes.data_as(ct.POINTER(ct.c_ubyte))

    def start_acquisition(self, focus: float, temp_min: float, temp_max: float):
        # Foco
        ret = self.libir.evo_irimager_set_focusmotor_pos(ct.c_float(focus))
        time.sleep(4)

        # Paleta
        palette = self.PALETTE_OPTIONS.get(self.palette_id)
        ret = self.libir.evo_irimager_set_palette(palette.encode('utf-8'))

        self.libir.evo_irimager_set_palette_scale(ct.c_int(1))
        self.libir.evo_irimager_set_palette_manual_temp_range(ct.c_float(temp_min), ct.c_float(temp_max))

        while chr(cv2.waitKey(1) & 255) != self.key_exit:
            ret = self.libir.evo_irimager_get_thermal_palette_image_metadata(
                self.thermal_width, self.thermal_height, self.npThermalPointer,
                self.palette_width, self.palette_height, self.npImagePointer,
                ct.byref(self.metadata))

            if ret != 0:
                print(f"Erro ao adquirir imagem: {ret}")
                continue

            temperatures = (self.np_thermal.reshape(self.thermal_height.value, self.thermal_width.value) - 1000.0) / 10.0
            temperatures = np.clip(temperatures, temp_min, temp_max)

            if temp_max != temp_min:
                normalized_img = ((temperatures - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
            else:
                normalized_img = np.zeros_like(temperatures, dtype=np.uint8)

            colormap = self.OPENCV_PALETTES.get(self.palette_id, cv2.COLORMAP_JET)
            colored_img = cv2.applyColorMap(normalized_img, colormap)
            scale_bar = self.criar_barra_escala(temp_min, temp_max, colormap, colored_img.shape[0])
            # **Resize scale bar to match the height of the thermal image**
            scale_bar_resized = cv2.resize(scale_bar, (scale_bar.shape[1], colored_img.shape[0]))
            final_img = np.hstack((colored_img, scale_bar_resized))

            cv2.imshow("Thermal Image with Scale", final_img)

        cv2.imwrite("thermal_image_with_scale.png", final_img)
        print("📸 Imagem térmica salva com a barra de escala!")

    def close(self):
        self.libir.evo_irimager_terminate()

    @staticmethod
    def criar_barra_escala(temp_min, temp_max, colormap, height):
        scale_width = 50
        border_thickness = 5
        scale_bar = np.linspace(temp_max, temp_min, height).reshape(height, 1)
        scale_bar = ((scale_bar - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
        scale_bar_colored = cv2.applyColorMap(scale_bar, colormap)
        scale_bar_colored = cv2.resize(scale_bar_colored, (scale_width, height))

        scale_bar_with_border = cv2.copyMakeBorder(
            scale_bar_colored, border_thickness, border_thickness,
            border_thickness, border_thickness, cv2.BORDER_CONSTANT, value=(255, 255, 255))

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        text_color = (0, 0, 0)

        cv2.putText(scale_bar_with_border, f"{temp_max:.1f}C",
                    (5, border_thickness + 15), font, font_scale, text_color, font_thickness, cv2.LINE_AA)
        cv2.putText(scale_bar_with_border, f"{temp_min:.1f}C",
                    (5, height + border_thickness - 5), font, font_scale, text_color, font_thickness, cv2.LINE_AA)

        return scale_bar_with_border
