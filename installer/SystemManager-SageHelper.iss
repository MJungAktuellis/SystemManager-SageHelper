; Inno-Setup-Skript für SystemManager-SageHelper.
; Dieses Skript wird über scripts/build_installer.ps1 mit Version/Publisher-Parametern aufgerufen.

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#ifndef MyAppPublisher
  #define MyAppPublisher "SystemManager Team"
#endif

#ifndef MyAppExeName
  #define MyAppExeName "SystemManager-SageHelper.exe"
#endif

#ifndef MyBuildRoot
  #define MyBuildRoot "build"
#endif

[Setup]
AppId={{3A4AF658-9A21-4A08-9E2A-57F23050B20D}
AppName=SystemManager-SageHelper
AppVersion={#MyAppVersion}
AppVerName=SystemManager-SageHelper {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://example.invalid/systemmanager
AppSupportURL=https://example.invalid/systemmanager/support
AppUpdatesURL=https://example.invalid/systemmanager/releases
DefaultDirName={autopf}\SystemManager-SageHelper
DefaultGroupName=SystemManager-SageHelper
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir={#MyBuildRoot}\installer
OutputBaseFilename=SystemManager-SageHelper-{#MyAppVersion}-setup
UninstallDisplayName=SystemManager-SageHelper
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=SystemManager-SageHelper Installer
VersionInfoCopyright=Copyright (c) {#MyAppPublisher}
SetupLogging=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Verknüpfungen:"; Flags: unchecked

[Dirs]
; ProgramData ist bewusst getrennt, damit Laufzeitdaten schreibbar bleiben.
Name: "{commonappdata}\SystemManager-SageHelper"
Name: "{commonappdata}\SystemManager-SageHelper\config"
Name: "{commonappdata}\SystemManager-SageHelper\logs"

[Files]
Source: "{#MyBuildRoot}\staging\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SystemManager-SageHelper"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SystemManager-SageHelper"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Öffnet nach Installation optional direkt die GUI.
Filename: "{app}\{#MyAppExeName}"; Description: "SystemManager-SageHelper starten"; Flags: nowait postinstall skipifsilent

[Code]
procedure SetProgramDataAcl;
var
  ResultCode: Integer;
  ProgramDataPath: String;
begin
  ProgramDataPath := ExpandConstant('{commonappdata}\SystemManager-SageHelper');

  { Vergibt Änderungsrechte für normale Benutzer auf ProgramData-Unterordner.
    Damit können Konfigurationen und Logs ohne erhöhte Rechte geschrieben werden. }
  if not Exec(
    ExpandConstant('{cmd}'),
    '/C icacls "' + ProgramDataPath + '" /grant *S-1-5-32-545:(OI)(CI)(M) /T /C',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
  begin
    Log('Konnte ACL-Anpassung für ProgramData nicht ausführen.');
  end
  else
  begin
    Log('ACL-Anpassung für ProgramData beendet mit ExitCode ' + IntToStr(ResultCode));
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SetProgramDataAcl;
  end;
end;
