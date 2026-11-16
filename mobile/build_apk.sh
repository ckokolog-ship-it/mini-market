#!/bin/sh
# build_apk.sh -- the APK of the mini market, from this folder (mobile): the pages copied in (npm run sync),
# the key of the APKs made the first time (keystore/, not in git), gradle. Needs node, JDK 21 and the
# Android SDK (ANDROID_HOME); on Windows: build_apk.ps1, all of it in Docker.
#
#     sh build_apk.sh            ->  apk/MiniMarket-1.0.<yymmddhh>.apk
set -e
cd "$(dirname "$0")"
if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
npm run sync
if [ ! -f keystore/sideload.properties ]; then
  # once: a key of its own for this shop; its password random, beside it (keep the folder, back it up)
  mkdir -p keystore
  PW=$(node -e "console.log(require('crypto').randomBytes(18).toString('hex'))")
  keytool -genkeypair -keystore keystore/sideload.keystore -storetype PKCS12 -alias minimarket \
    -keyalg RSA -keysize 3072 -validity 10000 -storepass "$PW" -keypass "$PW" \
    -dname "CN=Mini market, O=Mini market" > /dev/null 2>&1
  printf 'storeFile=sideload.keystore\nalias=minimarket\npassword=%s\n' "$PW" > keystore/sideload.properties
  echo "== a new key of the APKs: mobile/keystore (keep it: the next APKs install over this one only with it)"
fi
export MM_VERSION_CODE="${MM_VERSION_CODE:-$(date +%y%m%d%H)}"
cd android
sed -i 's/\r$//' gradlew
sh ./gradlew assembleRelease --no-daemon -q
cd ..
mkdir -p apk
cp android/app/build/outputs/apk/release/app-release.apk "apk/MiniMarket-1.0.$MM_VERSION_CODE.apk"
echo "== apk/MiniMarket-1.0.$MM_VERSION_CODE.apk"
