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

android.api = 33
android.minapi = 21
android.ndk = 25b

[buildozer]
log_level = 2
android.accept_sdk_license = True
android.skip_update = True
android.sdk_path = /home/runner/.buildozer/android/platform/android-sdk
