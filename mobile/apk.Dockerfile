# apk.Dockerfile -- what builds the APK of the mini market on a computer without Android Studio: JDK 21,
# node 22 and the Android SDK. build_apk.ps1 (Windows) makes it once and runs build_apk.sh in it, on this
# folder (the APK and the key of the APKs stay here: mobile/apk, mobile/keystore). The first time it
# downloads about 1.5 GB (the SDK, gradle) and takes 10-20 minutes; the next ones are quicker.
FROM eclipse-temurin:21-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends unzip curl ca-certificates \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*
ENV ANDROID_HOME=/opt/android-sdk
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
 && curl -fsSL -o /tmp/tools.zip https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
 && unzip -q /tmp/tools.zip -d $ANDROID_HOME/cmdline-tools && mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
 && rm /tmp/tools.zip \
 && yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses > /dev/null \
 && $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platforms;android-36" "build-tools;35.0.0" > /dev/null
WORKDIR /src/mobile
CMD ["sh", "build_apk.sh"]
