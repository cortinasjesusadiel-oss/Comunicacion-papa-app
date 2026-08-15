[app]
title = Control Papa Asistente
package.name = controlpapa
package.domain = org.jesus
source.include_exts = py,png,jpg,kv,atlas
source.dir = .
version = 1.0
requirements = python3,kivy
orientation = portrait
android.permissions = INTERNET

[buildozer]
log_level = 2
android.accept_sdk_license = True
# Forzamos una versión que no requiere descarga externa
android.sdk_build_tools_version = 30.0.3
android.api = 30
android.ndk = 23b
