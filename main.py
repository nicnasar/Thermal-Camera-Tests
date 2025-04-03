from classes import *

camera = EvoIRCamera(palette_id=11)
camera.start_acquisition(focus=80, temp_min=20.0, temp_max=40.0)
camera.close()