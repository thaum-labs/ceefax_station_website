# Ceefax Station Installers

This directory contains Windows installer executables for Ceefax Station.

## Current Installer

- **CeefaxStation-Setup-0.1.0.exe** - Version 0.1.0-alpha

## Building New Installers

When you want to create a new installer for a new version:

1. **Update the version** (if needed):
   - Update `VERSION` file in the repository root
   - Update `CHANGELOG.json` with new changes

2. **Build the installer**:
   ```powershell
   cd C:\Users\tobot\Desktop\ceefax-installer-build
   .\build_installer.ps1
   ```

3. **Copy the new installer here**:
   ```powershell
   Copy-Item "C:\Users\tobot\Desktop\ceefax-installer-build\dist\CeefaxStation-Setup-X.X.X.exe" -Destination "installers\CeefaxStation-Setup-X.X.X.exe"
   ```

4. **Remove the old installer** (if replacing):
   ```powershell
   Remove-Item "installers\CeefaxStation-Setup-OLD_VERSION.exe"
   ```

5. **Commit and push**:
   ```bash
   git add installers/
   git commit -m "Add installer for version X.X.X"
   git push
   ```

## Notes

- Installers are built using PyInstaller and Inno Setup
- The installer bundles all dependencies into a single executable
- Installers may lag behind the latest code on GitHub
- Users can always use the manual installation method for the latest code

