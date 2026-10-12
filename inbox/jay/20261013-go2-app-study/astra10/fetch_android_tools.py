from acquire import fetch, ROOT
import concurrent.futures, hashlib, zipfile, json

ITEMS = [
 ('https://dl.google.com/android/repository/commandlinetools-win-16111833_latest.zip','android-cmdline.zip','57d04f2d75eb8e8fffc5000a987e5de4b5a63e9d','sdk/cmdline-tools/staging'),
 ('https://dl.google.com/android/repository/platform-tools_r37.0.1-win.zip','android-platform.zip','e03e78b1d80b396f1c3358e31251cb31740e1110','sdk'),
 ('https://dl.google.com/android/repository/emulator-windows_x64-16428233.zip','android-emulator.zip','488ed747e82de7e9bb5247becd1ac043c7e5e85d','sdk'),
 ('https://dl.google.com/android/repository/sys-img/google_apis/x86_64-30_r16.zip','android-image.zip','6ae21030eaadc041078444d3798e4b399f3e787d','sdk/system-images/android-30/google_apis'),
]
def one(item):
    url,name,expected,folder=item
    p=fetch(url,name)
    actual=hashlib.file_digest(p.open('rb'),'sha1').hexdigest()
    if actual!=expected: raise ValueError('Google repository SHA1 mismatch: '+name)
    dst=ROOT/'tools'/folder
    dst.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(p) as z:
        for n in z.namelist():
            if not (dst/n).resolve().is_relative_to(dst.resolve()): raise ValueError('Unsafe ZIP entry')
        z.extractall(dst)
    print('verified/extracted',name,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    list(executor.map(one,ITEMS))
