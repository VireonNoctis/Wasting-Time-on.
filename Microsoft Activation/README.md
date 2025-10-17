```markdown
# Microsoft Activation Scripts (MAS) Utility

A comprehensive batch script for Windows and Office activation, diagnostics, and licensing repair.  
This version of the script provides a menu-driven interface and automated PowerShell routines to ensure reliable activation on supported systems.

---

## 🧩 Overview

This script automates common activation and licensing tasks for Microsoft products.  
It checks the system environment, ensures required services and PowerShell components are running, and provides multiple activation methods depending on your OS version and needs.

It includes safeguards, system checks, and color-coded feedback for easier debugging and safe execution.

---

## ⚙️ Features

- 🧠 **Environment Verification**
  - Detects Windows build, architecture, and SKU
  - Ensures PowerShell is in `FullLanguage` mode
  - Handles x86/x64/ARM64 re-launches automatically
  - Validates `Null` service, `QuickEdit`, and PowerShell access

- 🔐 **Activation Modes**
  | Mode | Description | Supports |
  |------|--------------|-----------|
  | **HWID** | Permanent Digital License activation | Windows 10 / 11 |
  | **KMS38** | Activates Windows until 2038 | Windows 7+ |
  | **Online KMS** | Connects to online KMS servers | Windows / Office |
  | **Ohook** | Office-specific activation (Click-to-Run) | Microsoft Office |
  | **TSforge** | Universal activation + ESU | Windows / Office / ESU |

- 🪟 **Extras**
  - Extract `$OEM$` folder for pre-activated installations
  - Download genuine Windows / Office ISOs
  - Change Windows or Office edition
  - Check activation status
  - Troubleshooting tools (fix licensing, repair PowerShell, etc.)

---

## 🧭 How It Works

1. **Initialization**
   - Sets up the proper environment variables.
   - Checks for administrative privileges.
   - Re-launches the script as Administrator if needed.

2. **System Validation**
   - Detects system build, PowerShell version, and edition.
   - Checks for broken services or blocked hosts.
   - Scans for malware (e.g., KMSPico, AutoPico).

3. **Activation**
   - Runs the selected activation mode.
   - Generates or installs license tickets (e.g., `GenuineTicket.xml`).
   - Rebuilds licensing services if corrupted.

4. **Post-Activation**
   - Confirms genuine status.
   - Restores Windows region and registry values.
   - Displays results in color-coded output.

---

## 💡 Menu Navigation

| Option | Function |
|--------|-----------|
| `1` | HWID (Digital License) |
| `2` | Ohook (Office) |
| `3` | TSforge (Windows / Office / ESU) |
| `4` | KMS38 (Up to Year 2038) |
| `5` | Online KMS |
| `6` | Check Activation Status |
| `7` | Change Windows Edition |
| `8` | Change Office Edition |
| `9` | Troubleshoot |
| `E` | Extras (OEM, Genuine ISO, etc.) |
| `H` | Help |
| `0` | Exit |

---

## 🧩 OEM Folder Integration

The script can generate a `$OEM$` structure for automated activation during Windows installation.  
When placed in your Windows installation media, activation runs right after setup.

**Path structure:**
```

$OEM$$$\Setup\Scripts\MAS_AIO.cmd
$OEM$$$\Setup\Scripts\SetupComplete.cmd

```

This ensures the activation script triggers after setup completion.

---

## 🔧 Troubleshooting

If any errors occur, the script automatically displays diagnostic messages and links, such as:

- `fix_service` — Repair Null service or dependencies  
- `fix_powershell` — Enable PowerShell FullLanguage mode  
- `troubleshoot` — Common issues and general repair guide  
- `remove_malware` — Remove known malware activators  
- `licensing-servers-issue` — Fix blocked activation endpoints  

You can also manually open the **Troubleshoot** option from the main menu.

---

## 🧱 Requirements

- Windows Vista → Windows 11 or Server equivalents  
- PowerShell (Windows edition, not Core)  
- Administrative privileges  
- Internet connection for online activation methods  

---

## 📜 License

This repository and its contents are shared for **educational and diagnostic use only**.  
It is meant to help understand how licensing, PowerShell, and activation processes work internally.  

Use responsibly in accordance with your local laws and software license agreements.

---

## 💬 Credits

- [massgrave.dev](https://massgrave.dev) – Original Microsoft Activation Scripts project  
- Community contributors for continued updates and maintenance  
```

---

## ⚡ 2. SIMPLIFIED CLEAN VERSION

```markdown
# Microsoft Activation Script

A simple Windows batch tool to check, fix, and activate Windows or Office.

---

## 🚀 How to Use

1. **Download and extract** the script folder.  
2. **Right-click → Run as administrator.**  
3. Wait for the menu to appear.  
4. Choose your option using the keyboard (1–9, E, H, or 0).  

---

## 🧩 Main Options

| Option | Description |
|--------|-------------|
| 1 | HWID – Digital license for Windows 10/11 |
| 2 | Ohook – Activates Microsoft Office |
| 3 | TSforge – For Windows, Office, and ESU updates |
| 4 | KMS38 – Activates Windows until 2038 |
| 5 | Online KMS – Internet-based activation |
| 6 | Check activation status |
| 7 | Change Windows edition |
| 8 | Change Office edition |
| 9 | Troubleshooting tools |
| E | Extras (OEM folder, genuine ISOs) |
| 0 | Exit the script |

---

## 🧰 Troubleshooting

If you see an error:
- Make sure **PowerShell** is installed and working.
- Check your **Internet connection**.
- **Disable antivirus temporarily** if it blocks the script.
- Restart and rerun as **Administrator**.

---

## 💾 OEM Folder

Use the **Extras → Extract $OEM$ Folder** option to auto-activate during Windows setup.  
This creates:
```

$OEM$$$\Setup\Scripts\MAS_AIO.cmd

```

Put this folder in your Windows installation media to automate activation.

---

## 📋 Notes

- Works on **Windows Vista → Windows 11** and their **Server versions**.  
- Requires **PowerShell (not Core)**.  
- Internet needed for Online/KMS modes.

---

## 🧑‍💻 Credits

- Script base by [massgrave.dev](https://massgrave.dev)  
- Adapted and documented by community contributors.  

```
