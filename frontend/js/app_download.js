/**
 * Link tải APK app Android.
 * Đổi apkUrl khi có bản build mới (tmpfiles, GitHub Releases, hoặc /downloads/ trên server).
 */
(function () {
  const APK_EXTERNAL =
    "https://tmpfiles.org/dl/wOwpTFn4Tcm2/app-release.apk";
  const APK_LOCAL = "/downloads/AI_Translator_v1.0.1.apk";
  const APK_FILENAME = "AI_Translator.apk";

  function getApkUrl() {
    return APK_EXTERNAL || APK_LOCAL;
  }

  function downloadApk() {
    const url = getApkUrl();
    const a = document.createElement("a");
    a.href = url;
    a.download = APK_FILENAME;
    a.rel = "noopener noreferrer";
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  window.APP_DOWNLOAD = {
    externalUrl: APK_EXTERNAL,
    localUrl: APK_LOCAL,
    fileName: APK_FILENAME,
    getUrl: getApkUrl,
    download: downloadApk,
  };

  function syncApkLinks() {
    const url = getApkUrl();
    document
      .querySelectorAll(
        ".btn-download-apk, #homeDownloadApk, #installMobileBtn, #ctaDownloadApk",
      )
      .forEach(function (el) {
        el.href = url;
        el.setAttribute("download", APK_FILENAME);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncApkLinks);
  } else {
    syncApkLinks();
  }
})();
