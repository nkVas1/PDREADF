; ──────────────────────────────────────────────────────────────
;  PDREADF – Inno Setup Installer Script
; ──────────────────────────────────────────────────────────────
;  Compile with Inno Setup 6+  (https://jrsoftware.org/isinfo.php)
;
;  Prerequisites:
;    1. Run  build.bat  (or the GitHub Actions workflow) first.
;    2. dist\PDREADF.exe must exist.
;
;  The resulting Setup_PDREADF.exe installs the application, creates
;  a Start Menu shortcut, registers .pdf file-association (optional),
;  and provides a standard Add/Remove Programs uninstaller.
; ──────────────────────────────────────────────────────────────

#define MyAppName      "PDREADF"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "nkVas1"
#define MyAppURL       "https://github.com/nkVas1/PDREADF"
#define MyAppExeName   "PDREADF.exe"

[Setup]
AppId={{B8F3C2A1-4D5E-6F70-8192-A3B4C5D6E7F8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=Setup_{#MyAppName}_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc";    Description: "Associate with .pdf files"; GroupDescription: "File associations:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Optional .pdf file association (only when user ticks the checkbox)
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids";            ValueType: string; ValueName: "PDREADF.PDF"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\PDREADF.PDF";                     ValueType: string; ValueName: ""; ValueData: "PDF Document (PDREADF)"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\PDREADF.PDF\DefaultIcon";         ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\PDREADF.PDF\shell\open\command";  ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
