# 유령 키를 «하드웨어에서 온 것만» 막는다. 관리자 권한이 필요 없다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-27
# 근거: 2026-09-27 · Archon AK47 (VID_0C45 PID_800A) 의 볼륨 노브가
#       오작동해 VOL_UP 이 8 초에 9~17 번 들어온다. 스페이스도 들어온 적 있다.
#       장치를 끄려면 관리자 승격이 필요한데 원격 세션에 UAC 를 띄울 수 없다.
# 요지: 저수준 키보드 훅으로 **하드웨어에서 온** 음량·스페이스만 버린다.
#
# 왜 이것이 안전한가 `확인됨`
#     Chrome Remote Desktop 은 SendInput 으로 키를 넣는다. 그런 입력에는
#     LLKHF_INJECTED(0x10) 플래그가 붙는다. 훅에서 그 플래그를 보고
#     **주입된 것은 그대로 통과**시키고 **하드웨어 것만** 버린다.
#     곧 팀장이 원격으로 치는 키는 «하나도» 영향받지 않는다.
#
# 무엇을 막나
#     하드웨어發 VOLUME_UP / VOLUME_DOWN / MUTE
#     하드웨어發 SPACE
#     그 밖의 «모든» 키는 통과한다. 하드웨어 타자도 그대로 된다.
#
# 끄는 법
#     이 프로세스를 끝내면 훅이 «즉시» 풀린다. 재부팅 불필요.
#     Stop-Process -Name powershell 로 이 창만 닫으면 된다.

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

Add-Type @'
using System;
using System.Runtime.InteropServices;

public class PhantomBlock {
    public const int WH_KEYBOARD_LL = 13;
    public const int WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101;
    public const int WM_SYSKEYDOWN = 0x0104, WM_SYSKEYUP = 0x0105;
    public const uint LLKHF_INJECTED = 0x10;

    [StructLayout(LayoutKind.Sequential)]
    public struct KBDLLHOOKSTRUCT {
        public uint vkCode; public uint scanCode; public uint flags;
        public uint time; public IntPtr dwExtraInfo;
    }

    public delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr SetWindowsHookEx(int id, HookProc cb, IntPtr mod, uint thread);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool UnhookWindowsHookEx(IntPtr hk);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr CallNextHookEx(IntPtr hk, int code, IntPtr w, IntPtr l);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr GetModuleHandle(string name);

    public static IntPtr Hook = IntPtr.Zero;
    public static HookProc Callback = null;

    // 셈 · 무엇을 얼마나 버렸나
    public static long BlockedVol = 0, BlockedSpace = 0, PassedInjected = 0, PassedHw = 0;

    public static IntPtr Proc(int nCode, IntPtr wParam, IntPtr lParam) {
        if (nCode >= 0) {
            KBDLLHOOKSTRUCT k = (KBDLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(KBDLLHOOKSTRUCT));
            bool injected = (k.flags & LLKHF_INJECTED) != 0;
            if (injected) {
                PassedInjected++;              // **원격 입력은 손대지 않는다**
            } else {
                // 하드웨어에서 온 것
                if (k.vkCode == 0xAF || k.vkCode == 0xAE || k.vkCode == 0xAD) {
                    BlockedVol++;
                    return (IntPtr)1;          // 버린다
                }
                if (k.vkCode == 0x20) {
                    BlockedSpace++;
                    return (IntPtr)1;          // 버린다
                }
                PassedHw++;
            }
        }
        return CallNextHookEx(Hook, nCode, wParam, lParam);
    }

    public static bool Install() {
        Callback = new HookProc(Proc);
        Hook = SetWindowsHookEx(WH_KEYBOARD_LL, Callback, GetModuleHandle(null), 0);
        return Hook != IntPtr.Zero;
    }
    public static void Remove() { if (Hook != IntPtr.Zero) { UnhookWindowsHookEx(Hook); Hook = IntPtr.Zero; } }
}
'@

if (-not [PhantomBlock]::Install()) {
    Write-Output "  ** 훅 설치 실패 **"
    exit 1
}
Write-Output "  훅을 걸었다. 하드웨어發 음량·스페이스만 버린다"
Write-Output "  원격(주입) 입력은 «그대로» 통과한다"
Write-Output "  이 창을 닫으면 훅이 «즉시» 풀린다"
Write-Output ""

$state = "C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-lab\_out\loop\phantom-block.json"
$t0 = Get-Date
try {
    while ($true) {
        # 메시지 펌프 · 저수준 훅은 이것이 돌아야 콜백이 온다
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 50
        if (((Get-Date) - $t0).TotalSeconds -ge 10) {
            $t0 = Get-Date
            $o = [pscustomobject]@{
                when             = (Get-Date).ToString('s')
                blocked_volume   = [PhantomBlock]::BlockedVol
                blocked_space    = [PhantomBlock]::BlockedSpace
                passed_injected  = [PhantomBlock]::PassedInjected
                passed_hardware  = [PhantomBlock]::PassedHw
            }
            $o | ConvertTo-Json -Compress | Set-Content -Path $state -Encoding utf8
        }
    }
} finally {
    [PhantomBlock]::Remove()
    Write-Output "  훅을 풀었다"
}
