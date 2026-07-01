import java.util.Properties
import java.io.FileInputStream

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.app_duyvo26.app_web_view"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.app_duyvo26.app_web_view"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        // Configure release signing: use `key.properties` if present, otherwise fall back to debug signing
        release {
            // The `key.properties` file (placed in android/) should contain:
            // storeFile=release-keystore.jks
            // storePassword=your_store_password
            // keyAlias=release_key
            // keyPassword=your_key_password
            val keystorePropertiesFile = rootProject.file("key.properties")
            val hasKeystore = keystorePropertiesFile.exists()

            if (hasKeystore) {
                val keystoreProperties = Properties()
                FileInputStream(keystorePropertiesFile).use { keystoreProperties.load(it) }

                signingConfigs.create("release") {
                    storeFile = file(keystoreProperties.getProperty("storeFile"))
                    storePassword = keystoreProperties.getProperty("storePassword")
                    keyAlias = keystoreProperties.getProperty("keyAlias")
                    keyPassword = keystoreProperties.getProperty("keyPassword")
                }

                signingConfig = signingConfigs.getByName("release")
            } else {
                // Fallback to debug signing for local quick tests
                signingConfig = signingConfigs.getByName("debug")
            }
        }
    }
}

flutter {
    source = "../.."
}
