# Acer Swift Go 14 (SFG14-71) Fan Controller

Simple, direct hardware fan control script for Acer Swift Go 14 (`Swift SFG14-71`, Motherboard `Coral_RTH`) with TwinAir dual cooling fans on Arch Linux.

Uses only the Python standard library. Communicates directly through the Linux kernel ACPI driver (`/proc/acpi/call`) and reads real physical tachometer RPMs directly from Embedded Controller (EC) RAM (`/sys/kernel/debug/ec/ec0/io`). Zero background services, zero daemons, zero external dependencies.

---

## 1. Prerequisites

The script requires the kernel module `acpi_call`:

```bash
# For LTS Kernel:
sudo paru -S acpi_call-lts

# For Standard Kernel:
sudo paru -S acpi_call
```

---

## 2. Usage Commands

All commands are run using `sudo`:

```bash
cd ~/fan-control
```

### Check Live Status & RPMs
```bash
sudo python3 fan_control.py status
# or simply:
sudo python3 fan_control.py
```
Displays:
* Live CPU Temperature
* Fan 1 & Fan 2 ACPI Speed Register & Mode values
* Real physical tachometer RPM for Fan 1 (CPU) and Fan 2 (Secondary)

### Stop Fans (0% / Silent)
```bash
sudo python3 fan_control.py stop
# or:
sudo python3 fan_control.py 0
```
Turns off both physical fans completely (0 RPM).

### Medium Speed (50%)
```bash
sudo python3 fan_control.py medium
# or:
sudo python3 fan_control.py 50
```
Sets both fans to 50% duty cycle (~5700 RPM).

### Full Speed (100% Full Blast)
```bash
sudo python3 fan_control.py full
# or:
sudo python3 fan_control.py 100
```
Sets both fans to maximum speed (~8000 RPM full blast).

### Custom Percentage (0 - 100%)
```bash
sudo python3 fan_control.py 75
```
Sets both fans to any desired percentage duty cycle.

### Revert to Factory BIOS Auto
```bash
sudo python3 fan_control.py auto
```
Reverts hardware fan control back to the motherboard BIOS firmware automatic thermal management.

### Dynamic Temperature Curve (CLI Monitor)
```bash
sudo python3 fan_control.py curve
```
Monitors CPU temperatures continuously in your terminal and adapts fan speeds in real time:
* **`>= 55°C`** $\rightarrow$ **100%** (Full Speed ~8000 RPM)
* **`45°C - 55°C`** $\rightarrow$ **50%** (Medium Speed ~5700 RPM)
* **`< 45°C`** $\rightarrow$ **0%** (Silent / Stopped 0 RPM)
* **`>= 85°C`** $\rightarrow$ Emergency failsafe override (forces 100% full blast)

*(Press `Ctrl+C` at any time to cleanly stop and revert fans to factory BIOS Auto)*.

If you ever want to run the curve in the background of your terminal session:
```bash
sudo nohup python3 /home/vinit/fan-control/fan_control.py curve > /dev/null 2>&1 &
```

---

## 3. Hardware Architecture Reference

* **Motherboard:** Acer `Coral_RTH` (SFG14-71, Intel i5-13500H)
* **Fan 1 (CPU):**
  * Speed Register: `33026` (`0x8102`), range `0` to `100`%
  * Mode Register: `33030` (`0x8106`), `0xFF` = Manual, `0x05` = BIOS Auto
  * Tachometer: EC RAM Offset `0x13` (16-bit word `C1FR`)
* **Fan 2 (Secondary / Aux):**
  * Speed Register: `33282` (`0x8202`), range `0` to `100`%
  * Mode Register: `33286` (`0x8206`), `0xFF` = Manual, `0x05` = BIOS Auto
  * Tachometer: EC RAM Offset `0x15` (16-bit word `G1FR`)
* **ACPI Methods:** `\_SB.PC00.LPCB.EC0.FANW` (write) and `\_SB.PC00.LPCB.EC0.FANG` (read)
