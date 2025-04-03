from classes import *

camera = EvoIRCamera(palette_id=11)
camera.start_acquisition(focus=80, temp_min=25.0, temp_max=35.0)
camera.close()