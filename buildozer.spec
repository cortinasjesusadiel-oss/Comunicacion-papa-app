[app]
title = Control Papa Asistente
package.name = controlpapa
package.domain = org.jesus
source.include_exts = py,png,jpg,kv,atlas
source.dir = .
version = 1.5
requirements = python3,kivy,pyjnius,requests
orientation = portrait
android.permissions = INTERNET,RECORD_AUDIO,READ_CONTACTS,MODIFY_AUDIO_SETTINGS,WAKE_LOCK

android.api = 33
android.minapi = 21
android.ndk = 25b
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
android.accept_sdk_license = True
android.skip_update = True
android.sdk_path = /home/runner/.buildozer/android/platform/android-sdk
