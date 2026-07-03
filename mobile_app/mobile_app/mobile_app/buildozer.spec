[app]
title = МегаПриложение
package.name = megaapp
package.domain = org.example

source.dir = .
source.include_exts = py,kv,png,jpg,atlas
version = 1.0

requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions =

android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
