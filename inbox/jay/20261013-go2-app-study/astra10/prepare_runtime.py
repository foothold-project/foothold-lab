from pathlib import Path
import lzma
ROOT=Path(__file__).resolve().parent
tools=ROOT/'tools'
avd=tools/'avd/astra10_go2.avd'
avd.mkdir(parents=True,exist_ok=True)
(tools/'avd/astra10_go2.ini').write_text('avd.ini.encoding=UTF-8\npath=C:\\Tools\\astra10-tools\\avd\\astra10_go2.avd\ntarget=android-30\n')
(avd/'config.ini').write_text('''AvdId=astra10_go2
avd.ini.encoding=UTF-8
avd.ini.displayname=ASTRA10 isolated APK research
abi.type=x86_64
tag.id=google_apis
tag.display=Google APIs
image.sysdir.1=C:\\Tools\\astra10-tools\\sdk\\system-images\\android-30\\google_apis\\x86_64\\
hw.cpu.arch=x86_64
hw.cpu.ncore=2
hw.ramSize=2048
hw.gpu.enabled=yes
hw.gpu.mode=swiftshader_indirect
hw.keyboard=yes
hw.lcd.width=1080
hw.lcd.height=1920
hw.lcd.density=420
hw.camera.back=none
hw.camera.front=none
hw.audioInput=no
hw.audioOutput=no
disk.dataPartition.size=4G
fastboot.forceColdBoot=yes
showDeviceFrame=no
''')
with lzma.open(ROOT/'downloads/frida-server.xz','rb') as src:
    (tools/'frida-server').write_bytes(src.read())
print('Prepared isolated runtime. No real device selected.')
