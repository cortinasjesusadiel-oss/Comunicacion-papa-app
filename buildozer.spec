[app]

title = Control Papa Asistente
package.name = controlpapa
package.domain = org.jesus
source.include_exts = py,png,jpg,kv,atlas
source.dir = .
version = 1.0

# Requisitos estrictos de Kivy y Python
requirements = python3,kivy

orientation = portrait

[buildozer]
log_level = 2

# Forzar el aceptado automático de licencias de Android SDK
android.accept_sdk_license = True

# Especificar una versión de API estable y probada para evitar conflictos de herramientas
android.api = 33
android.min_api = 21
