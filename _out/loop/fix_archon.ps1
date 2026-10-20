# Archon AK47 의 «미디어 키 끝점» 을 끈다. 관리자 권한으로 돈다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-27
# 근거: USB\VID_0C45&PID_800A = Archon AK47 (BusReportedDeviceDesc 로 확인)
#       볼륨 노브 오작동으로 VOL_UP 이 8 초에 9~17 번 들어온다
# 요지: MI_01 (소비자 제어) 부터 끄고, 안 멈추면 MI_02·MI_03 까지.
#       **MI_00 (타자용) 은 «건드리지 않는다».** 광주에서 직접 치실 분의
#       타자는 그대로 된다.
#
# 되돌리기
#   Enable-PnpDevice -InstanceId '<같은 ID>' -Confirm:$false
#   또는 이 파일을 -Restore 로 돌린다. 재부팅 불필요.

param([switch]$Restore)

$ErrorActionPreference = 'Continue'
$Log = 'C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-lab\_out\loop\fix_archon.log'
function Say($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Write-Output $l; Add-Content -Path $Log -Value $l -Encoding utf8 }

# Archon AK47 의 끝점 · MI_00 은 «타자» 라 목록에 넣지 않는다
$Targets = @(
  'USB\VID_0C45&PID_800A&MI_01\A&85FD546&0&0001',
  'USB\VID_0C45&PID_800A&MI_02\A&85FD546&0&0002',
  'USB\VID_0C45&PID_800A&MI_03\A&85FD546&0&0003'
)

Add-Type -Namespace W -Name K -MemberDefinition '[DllImport("user32.dll")] public static extern short GetAsyncKeyState(int v);'
function Measure-Vol([int]$n = 120) {
  $c = 0
  for ($i = 0; $i -lt $n; $i++) {
    foreach ($vk in 0xAF, 0xAE, 0xAD) {
      if (([W.K]::GetAsyncKeyState($vk) -band 0x8000) -ne 0) { $c++; break }
    }
    Start-Sleep -Milliseconds 50
  }
  return $c
}

Say "=== 관리자 권한: $(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) ==="

if ($Restore) {
  Say "되돌린다 · 세 끝점을 다시 켠다"
  foreach ($id in $Targets) {
    try { Enable-PnpDevice -InstanceId $id -Confirm:$false -EA Stop; Say "  켰다 $id" }
    catch { Say "  실패 $id · $($_.Exception.Message)" }
  }
  Say "끝"
  exit 0
}

$before = Measure-Vol 120
Say "0 단계 · 끄기 «전» 음량 키: $before / 120 (6 초)"

$i = 0
foreach ($id in $Targets) {
  $i++
  try {
    Disable-PnpDevice -InstanceId $id -Confirm:$false -EA Stop
    Say "$i 단계 · 껐다 · $id"
  } catch {
    Say "$i 단계 · ** 실패 ** $id · $($_.Exception.Message)"
    continue
  }
  Start-Sleep -Seconds 2
  $after = Measure-Vol 120
  Say "$i 단계 · 끈 «뒤» 음량 키: $after / 120"
  if ($after -eq 0) {
    Say ""
    Say "**멈췄다.** 범인은 여기까지의 끝점이다."
    Say "안 끈 것: $(($Targets[$i..($Targets.Count-1)]) -join ' , ')"
    Say "MI_00 (타자용) 은 «안 건드렸다». 하드웨어 타자는 그대로 된다."
    break
  }
}

Say ""
Say "현재 상태"
foreach ($id in $Targets) {
  $d = Get-PnpDevice -InstanceId $id -EA SilentlyContinue
  Say "  $($d.Status)  $id"
}
$mi0 = Get-PnpDevice -InstanceId 'USB\VID_0C45&PID_800A&MI_00\A&85FD546&0&0000' -EA SilentlyContinue
Say "  $($mi0.Status)  MI_00 (타자용 · 안 건드림)"
Say "끝"
