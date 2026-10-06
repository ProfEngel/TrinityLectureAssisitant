#define TrinityVersion "0.19.1"
[Setup]
AppId={{AF228FA5-5812-489A-B39F-6F8AC8AD6A92}
AppName=Trinity Desktop
AppVersion={#TrinityVersion}
AppPublisher=Trinity
AppPublisherURL=https://profengel.github.io/TrinityLectureAssisitant/
DefaultDirName={localappdata}\Programs\Trinity
DefaultGroupName=Trinity
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=Trinity-{#TrinityVersion}-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Trinity.exe
WizardStyle=modern
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Trinity"; Filename: "{app}\Trinity.exe"
Name: "{autodesktop}\Trinity"; Filename: "{app}\Trinity.exe"
[Run]
Filename: "{app}\Trinity.exe"; Description: "Trinity einrichten"; Flags: nowait postinstall skipifsilent
; Uninstall intentionally preserves user-owned config, Memory and models.
