; Inno Setup script for ZeroArm Desktop
; Build after packaging/build_portable.py has produced dist/ZeroArmDesktop

#define MyAppName "ZeroArm Desktop"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "ZeroArm"
#define MyAppExeName "ZeroArmDesktop.exe"
#define MyAppSource "..\dist\ZeroArmDesktop"

[Setup]
AppId={{8F2E3A61-7C4D-4B9A-9F11-ZEROARM-DESKTOP}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\ZeroArm\Desktop
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ZeroArmDesktop-{#MyAppVersion}-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; Do not touch user data under %LOCALAPPDATA%\ZeroArm Desktop
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#MyAppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
  MsgBox('User data under LocalAppData\ZeroArm Desktop will be preserved.', mbInformation, MB_OK);
end;
