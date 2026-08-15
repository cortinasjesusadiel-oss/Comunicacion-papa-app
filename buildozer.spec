[app]

# (str) Title of your application
title = Control Papa Asistente

# (str) Package name
package.name = controlpapa

# (str) Package domain (needed for android packaging)
package.domain = org.jesus

# (list) Source files to include (let it include python files)
source.include_exts = py,png,jpg,kv,atlas

# (list) Application requirements
# Aquí indicamos que tu app necesita Python y Kivy para funcionar en el móvil
requirements = python3,kivy

# (str) Supported orientations
orientation = portrait

[buildozer]
# Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2
