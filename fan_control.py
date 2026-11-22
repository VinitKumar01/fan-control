#!/usr/bin/env python3
"""
Acer Swift Go 14 (SFG14-71) Fan Controller
Direct ACPI & EC Hardware Interface for TwinAir Dual Fan Cooling System.

Pure Python standard library only - no external dependencies or daemons.
"""
import os
import sys
import time
import glob

ACPI_CALL = "/proc/acpi/call"
EC_IO = "/sys/kernel/debug/ec/ec0/io"

# ACPI Register indices (Coral_RTH motherboard)
# Speed registers: 0-100 = Manual percentage duty cycle, 0xFF (255) = Auto/Release override
FAN1_SPEED = 33026  # 0x8102 (Fan 1 Speed: 0-100, 0xFF = Auto)
FAN1_MODE  = 33030  # 0x8106 (Fan 1 Mode: 0xFF = Manual, 0x05 = BIOS Auto)
FAN2_SPEED = 33282  # 0x8202 (Fan 2 Speed: 0-100, 0xFF = Auto)
FAN2_MODE  = 33286  # 0x8206 (Fan 2 Mode: 0xFF = Manual, 0x05 = BIOS Auto)

# EC RAM tachometer byte offsets
EC_FAN1_RPM = 0x13  # 16-bit word C1FR
EC_FAN2_RPM = 0x15  # 16-bit word G1FR


def check_root_and_env():
    """Ensure root privileges and required kernel interfaces are available."""
    if os.geteuid() != 0:
        print("[-] Permission denied: Must run with sudo.")
        print("    Usage: sudo python3 fan_control.py [status|stop|medium|full|auto|<0-100>]")
        sys.exit(1)

    if not os.path.exists(ACPI_CALL):
        os.system("modprobe acpi_call 2>/dev/null")
        if not os.path.exists(ACPI_CALL):
            print("[-] Error: /proc/acpi/call is not available.")
            print("    Please install acpi_call: sudo paru -S acpi_call-lts (or acpi_call)")
            sys.exit(1)

    if not os.path.exists(EC_IO):
        os.system("modprobe ec_sys write_support=1 2>/dev/null")


def call_acpi(cmd: str) -> str:
    """Send an ACPI call string and read the return value."""
    try:
        with open(ACPI_CALL, "w") as f:
            f.write(cmd)
        with open(ACPI_CALL, "r") as f:
            return f.read().strip("\x00 \n\r")
    except Exception as e:
        return f"Error: {e}"


def read_hardware_rpms() -> tuple[int, int]:
    """Read physical fan tachometer RPMs directly from EC RAM."""
    try:
        with open(EC_IO, "rb") as f:
            ec = f.read(256)
        rpm1 = ec[EC_FAN1_RPM] | (ec[EC_FAN1_RPM + 1] << 8)
        rpm2 = ec[EC_FAN2_RPM] | (ec[EC_FAN2_RPM + 1] << 8)
        return rpm1, rpm2
    except Exception:
        return 0, 0


def get_temperatures() -> tuple[float, float]:
    """Read CPU package and maximum core temperatures in °C directly from Intel DTS."""
    pkg_temp = None
    core_temps = []
    for path in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(os.path.join(path, "name"), "r") as f:
                name = f.read().strip()
            if "coretemp" in name:
                for tf in glob.glob(os.path.join(path, "temp*_input")):
                    lbl_f = tf.replace("_input", "_label")
                    try:
                        lbl = open(lbl_f).read().strip() if os.path.exists(lbl_f) else ""
                        val = int(open(tf).read().strip()) / 1000.0
                        if "Package" in lbl:
                            pkg_temp = val
                        else:
                            core_temps.append(val)
                    except Exception:
                        pass
        except Exception:
            pass

    max_c = max(core_temps) if core_temps else (pkg_temp or 45.0)
    pkg = pkg_temp if pkg_temp is not None else max_c
    return pkg, max_c


def get_cpu_temp() -> float:
    pkg, max_c = get_temperatures()
    return max(pkg, max_c)


def set_both_fans(pct: int):
    """Set both physical fans to manual percentage duty cycle (0-100)."""
    pct = max(0, min(100, int(pct)))
    # Enable Manual Mode (0xFF)
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN1_MODE} 0xFF")
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN2_MODE} 0xFF")
    # Apply speed duty cycle (0-100)
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN1_SPEED} {pct}")
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN2_SPEED} {pct}")


def set_bios_auto():
    """
    Revert both fans to original motherboard BIOS automatic control.
    Restores the firmware baseline operating speed (20% / 0x14)
    and enables BIOS Auto mode (0x05). The motherboard firmware then
    dynamically accelerates the fans as CPU/GPU load increases,
    and returns to baseline when cool.
    """
    # 1. Restore BIOS baseline idle speed (20% / 0x14) to wake EC from dead stop
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN1_SPEED} 20")
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN2_SPEED} 20")
    # 2. Hand control back to BIOS firmware (Mode 0x05)
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN1_MODE} 0x00")
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN2_MODE} 0x00")
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN1_MODE} 0x05")
    call_acpi(f"\\_SB.PC00.LPCB.EC0.FANW {FAN2_MODE} 0x05")


def show_status(wait_refresh=0.8):
    """Print current temperatures, ACPI registers, and live tachometers."""
    if wait_refresh > 0:
        time.sleep(wait_refresh)

    pkg_t, max_c = get_temperatures()
    rpm1, rpm2 = read_hardware_rpms()
    s1 = call_acpi(f"\\_SB.PC00.LPCB.EC0.FANG {FAN1_SPEED}")
    s2 = call_acpi(f"\\_SB.PC00.LPCB.EC0.FANG {FAN2_SPEED}")
    m1 = call_acpi(f"\\_SB.PC00.LPCB.EC0.FANG {FAN1_MODE}")
    m2 = call_acpi(f"\\_SB.PC00.LPCB.EC0.FANG {FAN2_MODE}")

    def parse_mode(val):
        return "Manual" if val.lower() in ("0xff", "0xef") else "Auto (BIOS)"

    print("-" * 52)
    print(f" CPU Package Temp    : {pkg_t:.1f} °C (Max Core: {max_c:.1f} °C)")
    print(f" Fan 1 Speed Setting : {s1:5s} | Mode: {parse_mode(m1)}")
    print(f" Fan 2 Speed Setting : {s2:5s} | Mode: {parse_mode(m2)}")
    print(f" Live Tachometer RPM : Fan 1: {rpm1} RPM | Fan 2: {rpm2} RPM")
    print("-" * 52)


def print_help():
    print("""Acer Swift Go 14 Fan Controller

Usage:
  sudo python3 fan_control.py [command]

Commands:
  status, (no args)   Display CPU temperature and live physical RPM tachometers
  stop, 0             Stop both fans immediately (0 RPM)
  medium, 50          Set both fans to medium speed (~5700 RPM)
  full, 100, max      Set both fans to full speed (~8000 RPM full blast)
  <0-100>             Set specific manual percentage duty cycle
  auto, bios          Revert control back to factory BIOS automatic control
  --help, -h          Show this help message
""")


def main():
    check_root_and_env()

    if len(sys.argv) == 1:
        show_status(wait_refresh=0)
        return

    arg = sys.argv[1].lower()

    if arg in ("--help", "-h", "help"):
        print_help()
    elif arg == "status":
        show_status(wait_refresh=0)
    elif arg in ("stop", "0"):
        set_both_fans(0)
        print("[✓] Both Fans STOPPED (0%)")
        show_status(wait_refresh=0.8)
    elif arg in ("medium", "50"):
        set_both_fans(50)
        print("[✓] Both Fans set to 50% (MEDIUM)")
        show_status(wait_refresh=0.8)
    elif arg in ("full", "100", "max"):
        set_both_fans(100)
        print("[✓] Both Fans set to 100% (FULL BLAST)")
        show_status(wait_refresh=0.8)
    elif arg in ("auto", "bios"):
        set_bios_auto()
        print("[✓] Both Fans reverted to BIOS AUTO")
        show_status(wait_refresh=0.8)
    elif arg.isdigit():
        val = int(arg)
        if not (0 <= val <= 100):
            print("[-] Error: Speed must be an integer between 0 and 100.")
            sys.exit(1)
        set_both_fans(val)
        print(f"[✓] Both Fans set to {val}%")
        show_status(wait_refresh=0.8)
    else:
        print(f"[-] Unknown command: '{arg}'")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
